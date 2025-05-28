import os
import logging
import time
from datetime import datetime
from typing import List, Set, Dict, Tuple, Optional
from dataclasses import dataclass
from functools import wraps

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from requests.exceptions import ReadTimeout, ConnectionError

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spotify_oldest_episodes.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def retry_on_timeout(max_retries=3, delay=1, backoff=2):
    """Decorador para reintentar operaciones que fallan por timeout."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (ReadTimeout, ConnectionError, SpotifyException) as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Falló después de {max_retries} intentos: {e}")
                        raise
                    
                    logger.warning(f"Intento {retries} falló, reintentando en {current_delay}s: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator

@dataclass
class EpisodeData:
    """Estructura de datos para un episodio."""
    uri: str
    release_date: str
    release_date_precision: str
    episode_id: str
    episode_name: str
    show_id: str
    show_name: str
    
    def get_sort_key(self) -> Tuple[int, int, int]:
        """Genera una clave de ordenamiento basada en la fecha de lanzamiento (más viejo = menor valor)."""
        try:
            date_parts = list(map(int, self.release_date.split('-')))
            
            if self.release_date_precision == 'year':
                return (date_parts[0], 1, 1)  # 1 de enero del año
            elif self.release_date_precision == 'month':
                return (date_parts[0], date_parts[1], 1)  # día 1 del mes
            
            return tuple(date_parts)
        except (ValueError, IndexError):
            # Fecha inválida, colocar al final (más nuevo)
            return (9999, 12, 31)
    
    def get_readable_date(self) -> str:
        """Retorna la fecha en formato legible."""
        try:
            sort_key = self.get_sort_key()
            return f"{sort_key[0]:04d}-{sort_key[1]:02d}-{sort_key[2]:02d}"
        except:
            return self.release_date

class SpotifyOldestEpisodeManager:
    """Gestor que guarda únicamente el episodio MÁS VIEJO no finalizado de cada podcast."""
    
    DEFAULT_LIMIT = 50
    REQUEST_TIMEOUT = 30
    DELAY_BETWEEN_REQUESTS = 0.2
    
    # Scopes necesarios
    REQUIRED_SCOPES = [
        'user-library-read',
        'user-library-modify',
        'user-read-playback-position'
    ]
    
    def __init__(self):
        """Inicializa el gestor de podcasts."""
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID', 'c798243109ac4543be01179d648837d9')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', '4ec223e6d89d43f5b87c1d6aa1b2a8c7')
        self.redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')
        
        self.sp = self._authenticate()
        self.request_count = 0
        
    def _authenticate(self) -> spotipy.Spotify:
        """Autentica con la API de Spotify."""
        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=' '.join(self.REQUIRED_SCOPES),
                requests_timeout=self.REQUEST_TIMEOUT
            )
            return spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            logger.error(f"Error en la autenticación: {e}")
            raise
    
    def _rate_limit_control(self):
        """Controla la velocidad de requests para evitar rate limiting."""
        self.request_count += 1
        time.sleep(self.DELAY_BETWEEN_REQUESTS)
        if self.request_count % 10 == 0:
            time.sleep(1)
    
    @retry_on_timeout(max_retries=3, delay=2, backoff=2)
    def _safe_request(self, request_func, *args, **kwargs):
        """Ejecuta un request de forma segura con control de rate limiting."""
        self._rate_limit_control()
        return request_func(*args, **kwargs)
    
    def _paginate_request(self, initial_request, next_func=None):
        """Maneja la paginación de requests de Spotify."""
        if next_func is None:
            next_func = self.sp.next
            
        current = initial_request
        
        while current and current.get('items'):
            yield from current['items']
            
            if current.get('next'):
                try:
                    current = self._safe_request(next_func, current)
                    if current is None:
                        break
                except Exception as e:
                    logger.error(f"Error en paginación: {e}")
                    break
            else:
                break
    
    @retry_on_timeout(max_retries=2, delay=1)
    def get_already_saved_episode_uris(self) -> Set[str]:
        """Obtiene los URIs de episodios ya guardados en 'Mis Podcasts'."""
        uris = set()
        
        try:
            saved_episodes = self._safe_request(
                self.sp.current_user_saved_episodes, 
                limit=self.DEFAULT_LIMIT
            )
            
            if saved_episodes:
                for item in self._paginate_request(saved_episodes):
                    if item and 'episode' in item and 'uri' in item['episode']:
                        uris.add(item['episode']['uri'])
                        
        except Exception as e:
            logger.error(f"Error al obtener episodios guardados: {e}")
        
        logger.info(f"Episodios ya guardados en 'Mis Podcasts': {len(uris)}")
        return uris
    
    def find_oldest_unfinished_episode_per_podcast(self) -> List[EpisodeData]:
        """
        Encuentra el episodio MÁS VIEJO no finalizado de cada podcast seguido.
        """
        oldest_episodes = []
        already_saved_uris = self.get_already_saved_episode_uris()
        
        try:
            # Obtener todos los podcasts seguidos
            shows = self._safe_request(
                self.sp.current_user_saved_shows, 
                limit=self.DEFAULT_LIMIT
            )
            
            if not shows:
                logger.warning("No se pudieron obtener los shows guardados")
                return []
            
            show_count = 0
            for show in self._paginate_request(shows):
                if not show or 'show' not in show:
                    continue
                    
                show_count += 1
                show_id = show['show']['id']
                show_name = show['show'].get('name', 'Desconocido')
                
                logger.info(f"Procesando podcast {show_count}: {show_name}")
                
                try:
                    oldest_episode = self._find_oldest_unfinished_episode_in_show(
                        show_id, show_name, already_saved_uris
                    )
                    
                    if oldest_episode:
                        oldest_episodes.append(oldest_episode)
                        logger.info(f"  ✓ Episodio más viejo encontrado: {oldest_episode.get_readable_date()} - {oldest_episode.episode_name[:60]}...")
                    else:
                        logger.info(f"  ✗ No se encontraron episodios válidos")
                        
                except Exception as e:
                    logger.error(f"Error procesando podcast {show_name}: {e}")
                    continue
                
                time.sleep(0.3)  # Pausa entre podcasts
                
        except Exception as e:
            logger.error(f"Error al obtener shows guardados: {e}")
            return []
        
        logger.info(f"\n=== RESUMEN ===")
        logger.info(f"Podcasts procesados: {show_count}")
        logger.info(f"Episodios más viejos encontrados: {len(oldest_episodes)}")
        
        return oldest_episodes
    
    def _find_oldest_unfinished_episode_in_show(self, show_id: str, show_name: str, already_saved_uris: Set[str]) -> Optional[EpisodeData]:
        """
        Encuentra el episodio MÁS VIEJO no finalizado en un podcast específico.
        """
        try:
            # Obtener todos los episodios del podcast
            show_episodes = self._safe_request(
                self.sp.show_episodes, 
                show_id, 
                limit=self.DEFAULT_LIMIT
            )
            
            if not show_episodes:
                return None
            
            valid_episodes = []
            
            # Recopilar todos los episodios válidos (no finalizados, no guardados)
            for episode in self._paginate_request(show_episodes):
                if not self._is_episode_valid_for_saving(episode, already_saved_uris):
                    continue
                
                episode_data = EpisodeData(
                    uri=episode['uri'],
                    release_date=episode['release_date'],
                    release_date_precision=episode.get('release_date_precision', 'day'),
                    episode_id=episode['id'],
                    episode_name=episode.get('name', 'Sin título'),
                    show_id=show_id,
                    show_name=show_name
                )
                
                valid_episodes.append(episode_data)
            
            if not valid_episodes:
                return None
            
            # Ordenar por fecha (más viejo primero) y tomar el primero
            valid_episodes.sort(key=lambda ep: ep.get_sort_key())
            oldest_episode = valid_episodes[0]
            
            logger.debug(f"    Episodios válidos encontrados: {len(valid_episodes)}")
            logger.debug(f"    Más viejo: {oldest_episode.get_readable_date()}")
            
            return oldest_episode
            
        except Exception as e:
            logger.error(f"Error al procesar episodios del show {show_id}: {e}")
            return None
    
    def _is_episode_valid_for_saving(self, episode: Dict, already_saved_uris: Set[str]) -> bool:
        """
        Verifica si un episodio es válido para guardar:
        - Tiene datos básicos necesarios
        - No está ya guardado en 'Mis Podcasts'
        - No está marcado como completamente reproducido
        - No es contenido exclusivo
        """
        if not (episode and 'uri' in episode and 'release_date' in episode and 'id' in episode):
            return False
        
        # No guardar si ya está en 'Mis Podcasts'
        if episode['uri'] in already_saved_uris:
            return False
        
        # No guardar si está completamente reproducido
        resume_point = episode.get('resume_point', {})
        if resume_point.get('fully_played', False):
            return False
        
        # No guardar si es contenido exclusivo
        if episode.get('is_paywall_content', False):
            return False
        
        return True
    
    @retry_on_timeout(max_retries=3, delay=1)
    def save_oldest_episodes_to_library(self) -> None:
        """
        Función principal: Guarda el episodio más viejo no finalizado de cada podcast seguido.
        """
        logger.info("=== SPOTIFY OLDEST EPISODE MANAGER ===")
        logger.info(f"Usuario: bfigueroa99")
        logger.info(f"Fecha: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info("Objetivo: Guardar el episodio MÁS VIEJO no finalizado de cada podcast seguido")
        logger.info("="*60)
        
        # Encontrar los episodios más viejos
        oldest_episodes = self.find_oldest_unfinished_episode_per_podcast()
        
        if not oldest_episodes:
            logger.info("No se encontraron episodios para guardar.")
            return
        
        logger.info(f"\n=== GUARDANDO {len(oldest_episodes)} EPISODIOS ===")
        
        # Mostrar lista de episodios que se van a guardar
        logger.info("Episodios que se guardarán:")
        for i, episode in enumerate(oldest_episodes, 1):
            logger.info(f"  {i:2d}. {episode.get_readable_date()} - {episode.show_name}")
            logger.info(f"      {episode.episode_name}")
        
        logger.info("\nIniciando guardado...")
        
        # Guardar cada episodio
        success_count = 0
        for i, episode in enumerate(oldest_episodes, 1):
            try:
                self._safe_request(
                    self.sp.current_user_saved_episodes_add, 
                    [episode.uri]
                )
                success_count += 1
                logger.info(f"  ✓ {i:2d}/{len(oldest_episodes)} - Guardado: {episode.show_name}")
                
                time.sleep(0.5)  # Pausa entre guardados
                
            except Exception as e:
                logger.error(f"  ✗ {i:2d}/{len(oldest_episodes)} - Error guardando {episode.show_name}: {e}")
        
        logger.info(f"\n=== PROCESO COMPLETADO ===")
        logger.info(f"Episodios guardados exitosamente: {success_count}/{len(oldest_episodes)}")
        
        if success_count > 0:
            logger.info("Los episodios más viejos han sido guardados en 'Mis Podcasts'")
        
    def clean_finished_episodes(self) -> None:
        """Elimina episodios completamente reproducidos de 'Mis Podcasts'."""
        logger.info("=== LIMPIANDO EPISODIOS FINALIZADOS ===")
        
        try:
            saved_episodes = self._safe_request(
                self.sp.current_user_saved_episodes, 
                limit=self.DEFAULT_LIMIT
            )
            
            if not saved_episodes:
                logger.warning("No se pudieron obtener episodios guardados")
                return
            
            removed_count = 0
            processed_count = 0
            
            for item in self._paginate_request(saved_episodes):
                if not item or 'episode' not in item:
                    continue
                
                processed_count += 1
                episode = item['episode']
                episode_uri = episode['uri']
                episode_name = episode.get('name', 'Sin título')
                
                # Verificar si está completamente reproducido
                resume_point = episode.get('resume_point', {})
                if resume_point.get('fully_played', False):
                    try:
                        self._safe_request(
                            self.sp.current_user_saved_episodes_delete, 
                            [episode_uri]
                        )
                        removed_count += 1
                        logger.info(f"Eliminado (finalizado): {episode_name}")
                        time.sleep(0.3)
                    except Exception as e:
                        logger.error(f"Error al eliminar {episode_name}: {e}")
                
                if processed_count % 20 == 0:
                    logger.info(f"Procesados {processed_count} episodios...")
                    time.sleep(1)
            
            logger.info(f"=== LIMPIEZA COMPLETADA ===")
            logger.info(f"Episodios eliminados: {removed_count}")
            logger.info(f"Episodios procesados: {processed_count}")
            
        except Exception as e:
            logger.error(f"Error al limpiar episodios finalizados: {e}")

def main():
    """Función principal del script."""
    try:
        manager = SpotifyOldestEpisodeManager()
        
        # Opcional: limpiar episodios finalizados primero
        logger.info("1. Limpiando episodios finalizados...")
        manager.clean_finished_episodes()
        
        logger.info("\n2. Buscando y guardando episodios más viejos...")
        manager.save_oldest_episodes_to_library()
        
        logger.info("\n=== ¡PROCESO COMPLETADO EXITOSAMENTE! ===")
        
    except Exception as e:
        logger.error(f"Error en la ejecución principal: {e}")
        raise

if __name__ == '__main__':
    main()