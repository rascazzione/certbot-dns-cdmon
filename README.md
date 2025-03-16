# Certbot DNS CDmon Plugin

Plugin de autenticación DNS para Certbot que utiliza la API de CDmon para resolver el desafío dns-01.

## Descripción

Este plugin automatiza el proceso de completar un desafío dns-01 creando y posteriormente eliminando registros TXT utilizando la API de CDmon. Esto es especialmente útil para obtener certificados wildcard, que solo se pueden obtener a través de la validación DNS.

## Requisitos

- Certbot >= 1.1.0
- Python >= 3.6
- Una cuenta en CDmon con acceso a la API
- Una clave API de CDmon con permisos para gestionar registros DNS

## Instalación

### Desde PyPI

```bash
pip install certbot-dns-cdmon
```

### Desde el código fuente

```bash
git clone https://github.com/yourusername/certbot-dns-cdmon.git
cd certbot-dns-cdmon
pip install -e .
```

## Configuración

### Obtener la clave API de CDmon

1. Inicia sesión en tu panel de control de CDmon
2. Navega a la sección de API o Desarrolladores
3. Genera una nueva clave API con permisos para gestionar registros DNS

### Crear el archivo de credenciales

Crea un archivo INI con tus credenciales de CDmon. Por ejemplo, `/etc/letsencrypt/cdmon-credentials.ini`:

```ini
certbot_dns_cdmon:api_key = tu_clave_api_de_cdmon
certbot_dns_cdmon:domain = tudominio.com
```

Asegúrate de que este archivo tenga permisos restrictivos:

```bash
chmod 600 /etc/letsencrypt/cdmon-credentials.ini
```

## Uso

### Obtener un certificado

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 90 \
  -d example.com \
  -d *.example.com
```

### Renovación automática

Certbot recordará qué plugin utilizaste, por lo que la renovación automática funcionará sin problemas.

### Parámetros

| Parámetro | Descripción |
|-----------|-------------|
| `--authenticator dns-cdmon` | Selecciona el plugin de autenticación |
| `--dns-cdmon-credentials` | Ruta al archivo INI con las credenciales de CDmon |
| `--dns-cdmon-propagation-seconds` | Tiempo de espera para la propagación DNS antes de que el servidor ACME verifique el registro DNS (por defecto: 90, recomendado: >= 90) |

## Ejemplos

### Certificado para un dominio y su wildcard

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 90 \
  -d example.com \
  -d *.example.com
```

### Certificado para múltiples subdominios

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 90 \
  -d example.com \
  -d www.example.com \
  -d app.example.com
```

## Solución de problemas

### Verificar que el plugin está instalado

```bash
certbot plugins
```

Deberías ver `dns-cdmon` en la lista de plugins disponibles.

### Problemas comunes

1. **Error de autenticación**: Verifica que la clave API sea correcta.
2. **Error de permisos**: Asegúrate de que la clave API tenga permisos para gestionar registros DNS.
3. **Tiempo de propagación insuficiente**: Aumenta el valor de `--dns-cdmon-propagation-seconds` si la verificación falla.

## Seguridad

Protege tu archivo de credenciales como lo harías con la contraseña de tu cuenta de CDmon. Los usuarios que puedan leer este archivo pueden realizar llamadas API arbitrarias en tu nombre.

## Desarrollo

### Configuración del entorno de desarrollo

```bash
git clone https://github.com/yourusername/certbot-dns-cdmon.git
cd certbot-dns-cdmon
python -m venv venv
source venv/bin/activate
pip install -e .
```

### Ejecutar pruebas

```bash
python -m unittest discover
```

## Licencia

Este proyecto está licenciado bajo la Licencia Apache 2.0 - ver el archivo LICENSE para más detalles.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue o un pull request en GitHub.