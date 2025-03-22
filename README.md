# Certbot DNS CDmon Plugin

Plugin de autenticación DNS para Certbot que utiliza la API de CDmon para resolver el desafío dns-01, ideal para obtener certificados Wildcard.

---

## Descripción

Este plugin automatiza el proceso de completar un desafío dns-01 creando y eliminando registros TXT mediante la API de CDmon. Esto es especialmente útil para obtener certificados Wildcard, que requieren validación DNS.

---

## Características

- Creación y eliminación automática de registros TXT para validación ACME
- Soporte para dominios y subdominios múltiples
- **Detección automática de dominios** - No es necesario especificar el dominio en el archivo de credenciales
- Manejo de reintentos automáticos para solicitudes a la API
- Validación robusta de credenciales y respuestas de la API
- Logging detallado para facilitar la depuración

---

## Requisitos

- **Certbot**: versión ≥ 1.1.0 (compatible con 3.3.0 y posteriores)
- **Python**: versión ≥ 3.6
- Cuenta en CDmon con acceso a la API.
- Clave API de CDmon con permisos para gestionar registros DNS.
- (Opcional) Entorno virtual (por ejemplo, mediante Conda o venv) para evitar problemas de permisos y dependencias.

---

## Instalación

### Desde PyPI (actualmente en construcción, usar instalación en Código Fuente)

Instala el plugin directamente con pip:

```bash
pip install certbot-dns-cdmon
```

### Desde el código fuente

Si deseas clonar el repositorio y probar o modificar el código:

1. Clona el repositorio:
   ```bash
   git clone https://github.com/rascazzione/certbot-dns-cdmon.git
   cd certbot-dns-cdmon
   ```
2. Instala el plugin en modo editable:
   ```bash
   pip install -e .
   ```

*Nota:* Si usas **Miniconda** o **Anaconda**, crea y activa un entorno virtual para evitar conflictos y problemas de permisos. Por ejemplo:
```bash
conda create -n certbot-env python=3.8
conda activate certbot-env
```

---

## Configuración

### 1. Obtener la clave API de CDmon

1. Inicia sesión en tu panel de control de CDmon.
2. Navega a la sección de API o Desarrolladores.
3. Genera una nueva clave API con permisos para gestionar registros DNS.

### 2. Crear el archivo de credenciales

Crea un archivo INI con tus credenciales. Por ejemplo, en `/etc/letsencrypt/cdmon-credentials.ini` (o en otra ubicación si no dispones de permisos en `/etc/letsencrypt`):

```ini
dns_cdmon_api_key = tu_clave_api_de_cdmon
```

**Importante:**

- El parámetro `dns_cdmon_domain` ahora es **opcional**. El plugin detectará automáticamente el dominio base a partir de los dominios que estás validando.
- Si deseas especificar manualmente el dominio base (por ejemplo, si la detección automática no funciona correctamente), puedes añadir:
  ```ini
  dns_cdmon_domain = tudominio.com
  ```
- No uses comillas alrededor de los valores.
- Asegúrate de que el archivo tenga permisos restrictivos para proteger tu clave:

  ```bash
  chmod 600 /etc/letsencrypt/cdmon-credentials.ini
  ```
- Si no dispones de permisos para escribir en `/etc/letsencrypt`, coloca el archivo en un directorio de tu usuario, por ejemplo en `/home/tu_usuario/certbot/credentials.ini`.

---

## Uso

### Obtener un certificado

El comando básico para obtener un certificado (incluyendo el certificado wildcard) es:

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 180 \
  -d example.com \
  -d *.example.com
```

El plugin detectará automáticamente que `example.com` es el dominio base y lo utilizará para las operaciones con la API de CDmon.

Si usas un entorno virtual (por ejemplo, Conda) y no deseas usar `sudo`, puedes especificar directorios de configuración, trabajo y logs que sean escribibles:

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /home/tu_usuario/certbot/credentials.ini \
  --dns-cdmon-propagation-seconds 180 \
  -d example.com \
  -d *.example.com \
  --config-dir /home/tu_usuario/certbot/config \
  --work-dir /home/tu_usuario/certbot/work \
  --logs-dir /home/tu_usuario/certbot/logs
```

*Consejo:* Si usas Miniconda y tu entorno se llama, por ejemplo, `certbot-env`, asegúrate de ejecutar el comando desde ese entorno activado. Si necesitas usar `sudo`, recuerda que al elevar permisos se pierde la activación del entorno. En ese caso, utiliza la ruta completa al ejecutable de certbot dentro de tu entorno:
```bash
sudo /home/tu_usuario/miniconda3/envs/certbot-env/bin/certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /home/tu_usuario/certbot/credentials.ini \
  --dns-cdmon-propagation-seconds 90 \
  -d example.com \
  -d *.example.com
```

---

## Renovación automática

Una vez obtenido el certificado, Certbot recordará el plugin utilizado. La renovación automática se realizará sin necesidad de reconfigurar el plugin. Pero recuerda que la deberás configurar siguiendo las instrucciones:

Certbot can automatically renew the certificate in the background, but you may need to take steps to enable that functionality. See https://certbot.org/renewal-setup for instructions.

---

## Parámetros

| Parámetro                            | Descripción                                                                                                  |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `--authenticator dns-cdmon`          | Selecciona el plugin de autenticación DNS CDmon.                                                             |
| `--dns-cdmon-credentials`            | Ruta al archivo INI con las credenciales de CDmon.                                                           |
| `--dns-cdmon-propagation-seconds`      | Tiempo de espera para que se propague el registro DNS antes de la verificación (por defecto: 90, recomendado ≥ 90). |

---

## Ejemplos

### Certificado para un dominio y su wildcard

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 180 \
  -d example.com \
  -d *.example.com
```

### Certificado para múltiples subdominios

```bash
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 180 \
  -d example.com \
  -d www.example.com \
  -d app.example.com
```

### Certificado para múltiples dominios diferentes

Ahora puedes usar el mismo archivo de credenciales para validar diferentes dominios:

```bash
# Primer dominio
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 180 \
  -d example.com \
  -d *.example.com

# Segundo dominio (usando el mismo archivo de credenciales)
certbot certonly \
  --authenticator dns-cdmon \
  --dns-cdmon-credentials /etc/letsencrypt/cdmon-credentials.ini \
  --dns-cdmon-propagation-seconds 180 \
  -d otrodominio.com \
  -d *.otrodominio.com
```

---

## Funcionamiento interno

El plugin realiza las siguientes operaciones:

1. **Validación de credenciales**: Verifica que la clave API esté configurada correctamente.
2. **Detección automática de dominios**: 
   - Analiza los dominios que se están validando para determinar el dominio base.
   - Si se proporciona `dns_cdmon_domain` en el archivo de credenciales, lo utiliza como referencia.
   - Si no se proporciona, detecta automáticamente el dominio base a partir de los parámetros de certbot.
3. **Extracción de subdominios**: Procesa el nombre de validación para extraer el subdominio correcto.
   - Por ejemplo, si el nombre de validación es `_acme-challenge.sub.example.com`, el plugin extraerá `sub` como subdominio.
4. **Creación de registros TXT**: 
   - Verifica si ya existe un registro TXT para el desafío ACME.
   - Si existe, actualiza su valor.
   - Si no existe, crea un nuevo registro.
5. **Manejo de reintentos**: Implementa reintentos automáticos para las solicitudes a la API en caso de errores temporales.
6. **Limpieza**: Elimina los registros TXT una vez completada la validación.

El plugin utiliza el prefijo `_acme-challenge` para los registros TXT, siguiendo el estándar ACME para validación DNS.

---

## Solución de problemas

Aquí se listan algunos problemas comunes y sus soluciones:

### 1. Error de permisos: `[Errno 13] Permission denied: '/var/log/letsencrypt'`

- **Causa:** Certbot intenta escribir en directorios del sistema que requieren permisos de root.
- **Solución:**  
  - **Opción A:** Ejecuta el comando con `sudo` (pero recuerda que en entornos virtuales puede ser necesario usar la ruta completa al ejecutable).  
    ```bash
    sudo /ruta/a/tu/entorno/bin/certbot certonly [opciones...]
    ```
  - **Opción B:** Especifica directorios de configuración, trabajo y logs en rutas de tu usuario:
    ```bash
    certbot certonly \
      --authenticator dns-cdmon \
      --dns-cdmon-credentials /ruta/a/tu/credentials.ini \
      --dns-cdmon-propagation-seconds 90 \
      -d example.com \
      -d *.example.com \
      --config-dir /home/tu_usuario/certbot/config \
      --work-dir /home/tu_usuario/certbot/work \
      --logs-dir /home/tu_usuario/certbot/logs
    ```

### 2. Error de "command not found" al usar `sudo`

- **Causa:** Al usar `sudo`, se pierde el entorno virtual y el comando `certbot` no se encuentra en el PATH de root.
- **Solución:** Usa la ruta completa al ejecutable de certbot dentro de tu entorno virtual (por ejemplo, con Conda):
  ```bash
  sudo /home/tu_usuario/miniconda3/envs/tu_entorno/bin/certbot certonly [opciones...]
  ```

### 3. Credenciales mal configuradas

- **Error:** "Missing properties in credentials configuration file..." o "CDmon API key is required."
- **Causa:** El archivo INI de credenciales no contiene los nombres de propiedad esperados o los valores están vacíos.
- **Solución:** Asegúrate de que el archivo tenga el siguiente formato (sin comillas):
  ```ini
  dns_cdmon_api_key = tu_clave_api_de_cdmon
  ```
  Y establece los permisos correctos:
  ```bash
  chmod 600 /ruta/al/archivo/cdmon-credentials.ini
  ```

### 4. Problemas con la detección automática de dominios

- **Error:** "Could not determine base domain for X" o problemas al crear registros DNS.
- **Causa:** El plugin no pudo detectar automáticamente el dominio base a partir de los dominios que se están validando.
- **Solución:** 
  - Especifica manualmente el dominio base en el archivo de credenciales:
    ```ini
    dns_cdmon_api_key = tu_clave_api_de_cdmon
    dns_cdmon_domain = tudominio.com
    ```
  - Asegúrate de que los dominios que estás validando con `-d` sean dominios completos y correctos.
  - Revisa los logs para obtener más información sobre el proceso de detección.

### 5. Tiempo de propagación insuficiente

- **Causa:** El registro DNS no se propaga completamente antes de que el servidor ACME verifique la existencia del registro TXT.
- **Solución:** Incrementa el valor de `--dns-cdmon-propagation-seconds` (por ejemplo, 90 o superior). Si sigues teniendo problemas, verifica con herramientas externas (como [WhatsMyDNS](https://www.whatsmydns.net/)) que el registro se esté propagando correctamente.

### 6. Problemas de conexión o autenticación con la API de CDmon

- **Causa:** La clave API puede ser incorrecta o la cuenta de CDmon no tiene los permisos necesarios.
- **Solución:**  
  - Verifica en el panel de CDmon que la clave API es correcta y tiene permisos para gestionar registros DNS.
  - Revisa el log de Certbot (ubicado en `/var/log/letsencrypt/` o en el directorio de logs que hayas especificado) para obtener detalles adicionales.
  - El plugin ahora implementa reintentos automáticos para errores temporales de red, pero si persisten los problemas, verifica tu conexión a Internet.

### 7. Errores en la respuesta de la API

- **Causa:** La API de CDmon puede devolver errores por diversas razones (permisos insuficientes, límites de tasa, etc.).
- **Solución:**
  - Verifica los logs detallados para identificar el error específico.
  - Asegúrate de que tienes permisos para gestionar registros DNS para el dominio que estás intentando validar.
  - Comprueba en el panel de CDmon que tienes permisos para gestionar registros DNS para ese dominio.

### 8. Otros errores o dudas

- **Consejo:** Revisa el listado de plugins instalados con:
  ```bash
  certbot plugins
  ```
  Deberías ver `dns-cdmon` en la lista.
- Consulta la [Comunidad Let's Encrypt](https://community.letsencrypt.org) para obtener ayuda adicional o buscar soluciones a problemas específicos.

---

## Desarrollo

### Configuración del entorno de desarrollo

1. Clona el repositorio:
   ```bash
   git clone https://github.com/rascazzione/certbot-dns-cdmon.git
   cd certbot-dns-cdmon
   ```
2. Crea y activa un entorno virtual (por ejemplo, con venv):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
   O, si usas Conda:
   ```bash
   conda create -n certbot-env python=3.8
   conda activate certbot-env
   ```
3. Instala el plugin en modo editable:
   ```bash
   pip install -e .
   ```

### Ejecutar pruebas

Ejecuta la suite de tests para verificar que todo funcione correctamente:
```bash
python -m unittest discover
```

### Estructura del código

El plugin está organizado de la siguiente manera:

- `certbot_dns_cdmon/dns_cdmon.py`: Implementación principal del autenticador DNS.
- `certbot_dns_cdmon/dns_cdmon_test.py`: Tests unitarios para verificar la funcionalidad.
- `certbot_dns_cdmon/__init__.py`: Archivo de inicialización del paquete.

El código sigue las mejores prácticas de Python y los estándares PEP 8 para estilo de código.

---

## Licencia

Este proyecto está licenciado bajo la [Licencia Apache 2.0](http://www.apache.org/licenses/LICENSE-2.0).

---

## Contribuciones

Las contribuciones son bienvenidas. Si deseas colaborar, por favor abre un issue o un pull request en GitHub.

---

## Changelog

### v0.1.0
- Implementación inicial del plugin

### v0.2.0
- Refactorización del código para eliminar duplicación
- Mejora en el manejo de errores y validación de entradas
- Implementación de reintentos automáticos para solicitudes a la API
- Mejora en la cobertura de pruebas
- Documentación ampliada

### v0.3.0
- Implementación de detección automática de dominios
- El parámetro `dns_cdmon_domain` en el archivo de credenciales ahora es opcional
- Mejora en la gestión de múltiples dominios con un solo archivo de credenciales
- Actualización de la documentación para reflejar los cambios
