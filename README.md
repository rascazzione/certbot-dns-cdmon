# Certbot DNS CDmon Plugin

Plugin de autenticación DNS para Certbot que utiliza la API de CDmon para resolver el desafío dns-01, ideal para obtener certificados Wildcard.

---

## Descripción

Este plugin automatiza el proceso de completar un desafío dns-01 creando y eliminando registros TXT mediante la API de CDmon. Esto es especialmente útil para obtener certificados Wildcard, que requieren validación DNS.

---

## Requisitos

- **Certbot**: versión ≥ 1.1.0 (compatible con 3.3.0 y posteriores)
- **Python**: versión ≥ 3.6
- Cuenta en CDmon con acceso a la API.
- Clave API de CDmon con permisos para gestionar registros DNS.
- (Opcional) Entorno virtual (por ejemplo, mediante Conda o venv) para evitar problemas de permisos y dependencias.

---

## Instalación

### Desde PyPI

Instala el plugin directamente con pip:

```bash
pip install certbot-dns-cdmon
```

### Desde el código fuente

Si deseas clonar el repositorio y probar o modificar el código:

1. Clona el repositorio:
   ```bash
   git clone https://github.com/yourusername/certbot-dns-cdmon.git
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
dns_cdmon_domain = tudominio.com
```

**Importante:**

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

Una vez obtenido el certificado, Certbot recordará el plugin utilizado. La renovación automática se realizará sin necesidad de reconfigurar el plugin.

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

- **Error:** "Missing properties in credentials configuration file..."
- **Causa:** El archivo INI de credenciales no contiene los nombres de propiedad esperados.
- **Solución:** Asegúrate de que el archivo tenga el siguiente formato (sin comillas):
  ```ini
  dns_cdmon_api_key = tu_clave_api_de_cdmon
  dns_cdmon_domain = tudominio.com
  ```
  Y establece los permisos correctos:
  ```bash
  chmod 600 /ruta/al/archivo/cdmon-credentials.ini
  ```

### 4. Tiempo de propagación insuficiente

- **Causa:** El registro DNS no se propaga completamente antes de que el servidor ACME verifique la existencia del registro TXT.
- **Solución:** Incrementa el valor de `--dns-cdmon-propagation-seconds` (por ejemplo, 90 o superior). Si sigues teniendo problemas, verifica con herramientas externas (como [WhatsMyDNS](https://www.whatsmydns.net/)) que el registro se esté propagando correctamente.

### 5. Problemas de conexión o autenticación con la API de CDmon

- **Causa:** La clave API puede ser incorrecta o la cuenta de CDmon no tiene los permisos necesarios.
- **Solución:**  
  - Verifica en el panel de CDmon que la clave API es correcta y tiene permisos para gestionar registros DNS.
  - Revisa el log de Certbot (ubicado en `/var/log/letsencrypt/` o en el directorio de logs que hayas especificado) para obtener detalles adicionales.

### 6. Otros errores o dudas

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
   git clone https://github.com/yourusername/certbot-dns-cdmon.git
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

---

## Licencia

Este proyecto está licenciado bajo la [Licencia Apache 2.0](http://www.apache.org/licenses/LICENSE-2.0).

---

## Contribuciones

Las contribuciones son bienvenidas. Si deseas colaborar, por favor abre un issue o un pull request en GitHub.
