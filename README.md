# Spotify Podcast Manager

Una herramienta en Python para gestionar podcasts en Spotify, incluyendo funcionalidades para guardar y eliminar episodios de podcasts.

## Características

- **save_podcasts.py**: Script principal para gestionar y guardar episodios de podcasts
- **eliminar_todos_los_podcasts.py**: Utilidad para eliminar todos los podcasts guardados
- Manejo robusto de errores con reintentos automáticos
- Logging detallado de operaciones
- Soporte para autenticación OAuth de Spotify

## Requisitos

- Python 3.7+
- Cuenta de desarrollador de Spotify
- Credenciales de API de Spotify (Client ID, Client Secret)

## Instalación

1. Clona este repositorio:
```bash
git clone <URL_DEL_REPOSITORIO>
cd podcastspotify
```

2. Crea un entorno virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # En Linux/macOS
# o
.venv\Scripts\activate  # En Windows
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Configura tus credenciales de Spotify:
   - Crea una aplicación en [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
   - Copia el Client ID y Client Secret
   - Crea un archivo `.env` con tus credenciales:
```
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Uso

### Guardar podcasts
```bash
python save_podcasts.py
```

### Eliminar todos los podcasts
```bash
python eliminar_todos_los_podcasts.py
```

## Estructura del proyecto

```
├── save_podcasts.py           # Script principal
├── eliminar_todos_los_podcasts.py  # Utilidad de eliminación
├── requirements.txt           # Dependencias
├── .env                      # Variables de entorno (no incluido en git)
├── .gitignore               # Archivos ignorados por git
└── spotify_oldest_episodes.log  # Archivo de log
```

## Configuración de Spotify API

1. Ve a [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Crea una nueva aplicación
3. Configura la URI de redirección: `http://127.0.0.1:8888/callback`
4. Copia las credenciales a tu archivo `.env`

## Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## Notas de Seguridad

- **NUNCA** commits tus credenciales de Spotify al repositorio
- Usa variables de entorno o archivos `.env` para credenciales
- El archivo `.env` está incluido en `.gitignore` por seguridad
