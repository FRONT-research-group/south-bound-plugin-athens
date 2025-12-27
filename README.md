# 📡 Southbound Plugin API – CAMARA Integration for Athens Site Continuum

This project implements **Southbound Plugin** using [FastAPI](https://fastapi.tiangolo.com/) to provide service deployment and LCM over  Athens site (aeriOS based) continuum.The onboarding and management of the applications on the **Athens Site Continuum** is abstracted through CAMARA APIs.

---

## 🚀 Features

* ✅ Onboard application packages **to Athens Site Continuum** via CAMARA APIs
* ✅ Create and stop application instances
* ✅ Query instance state
* ✅ Fully documented with OpenAPI and Postman-ready import
* ✅ Dockerized for easy deployment
* ✅ Structured and maintainable Python project

---

## 📁 Project Structure

```
src/
├── app/
│   ├── api_clients/          # HTTP clients (e.g., CAMARA, Application Repo)
│   ├── models/               # Pydantic models for CAMARA + EaaS APIs
│   ├── routers/              # FastAPI route handlers
│   ├── utils/                # Utilities (e.g., logger setup)
│   ├── config.py             # Settings loaded from .env
│   └── main.py               # FastAPI app entrypoint
├── .env                      # Local environment configuration
├── Dockerfile
├── docker-compose.yml
├── README.md
├── openapi.json
└── requirements.txt
```

---

## ⚙️ Configuration

All runtime settings are configured via a `.env` file at the root of the project.

### Example `.env`:

```env
DEBUG = True
EAAS_APPLICATION_REPO_URL = "http://nginx/eaas-application-repository/api/v1"
CAMARA_ENDPOINT_URL = "http://continuum-camara-api:8000"
LOG_FILE=.log/southbound.log

# aeriOS Keycloak token endpoint (full URL)
aeriOS_TOKEN_URL=https://keycloak.front-research-group.eu/auth/realms/NCSRD/protocol/openid-connect/token

# OAuth2 client settings (client_id is required; secret depends on Keycloak client type)
aeriOS_CLIENT_ID="some_client_id"
aeriOS_CLIENT_SECRET="some_client_secret"  # leave empty if public client; set if confidential client

# Resource-owner credentials (password grant)
aeriOS_USERNAME="aerios-registered-user"
aeriOS_PASSWORD="password"

# Optional (often not required for password grant in Keycloak, but supported)
aeriOS_SCOPE=openid
```

These values are accessed through a centralized `Settings` class (using `pydantic-settings`) and injected where needed.

---

## 🧩 API Capabilities

| Endpoint                            | Purpose                                   |
| ----------------------------------- | ----------------------------------------- |
| `POST /application_onboarding`      | Onboard a new application                 |
| `POST /create_application_instance` | Start an instance of an onboarded app     |
| `POST /stop_application_instance`   | Stop a running application instance       |
| `GET /{instanceId}/state`           | Get current status of a specific instance |
| `GET /openapi.json`                 | OpenAPI spec (for use with Postman etc.)  |
| `GET /health`                       | Check app ir running                      |

---

## 📘 OpenAPI & Postman Support

This project includes auto-generated OpenAPI docs available at:

```
http://localhost:8000/openapi.json
```

### To import into Postman:

1. Start your FastAPI server:

   ```bash
   uvicorn src.app.main:app --reload
   ```

2. In Postman:

   * Click **Import** → **Link**
   * Paste: `http://localhost:8000/openapi.json`
   * Postman will generate a full collection automatically

3. Use Postman to test, authorize, and interact with the API!

or just import openapi.json file

---

## 🐳 Docker Setup

The project is fully containerized for consistent deployment and testing.

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
services:
  southbound-api:
    build: .
    ports:
      - "9080:8000"
    env_file:
      - .env
    volumes:
      - .:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - application-repository-network
#  We need to be in the same docker network as other EaaS components
networks:
  application-repository-network:
    external: true
```

### Run the app with Docker:

```bash
docker-compose up --build
```

Open your browser at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠 Development Notes

🧠 The CAMARA and EaaS clients are wrapped with httpx and managed via FastAPI dependencies, enabling clean request scoping and dependency injection.
⚙️ Shared configuration is accessed through a singleton Settings class defined in app.config, with values loaded from environment variables.
🔁 httpx.Client instances are cached using functools.lru_cache() to enable connection reuse and improve performance across requests.
🧪 Application logic is modularized across routers, models, storage, and api_clients packages to improve maintainability and separation of concerns.
🔐 Authentication towards aerOS is handled centrally in the Southbound plugin. At startup, the application acquires an OAuth2 access token from the aerOS Identity Management service (Keycloak) using credentials provided via environment variables (client_id, optional client_secret, username, and password).
🔑 The obtained aerOS access token is cached and automatically attached as a Bearer token to all outbound calls from the Southbound plugin to the CAMARA APIs. CAMARA, in turn, forwards this token when invoking aerOS APIs, allowing authorization to be validated by the aerOS API Gateway (Krakend) and IdM components.
🔄 Token acquisition and refresh are abstracted behind a dedicated token management layer, ensuring transparent reuse and renewal of credentials without impacting application logic

---

## ✅ Requirements

* Python 3.10+
* FastAPI
* httpx
* Pydantic v2
* pydantic-settings
* python-dotenv

Install dependencies with:

```bash
pip install -r requirements.txt
```

---

## ✍️ Authors
Architecture, design, and implementation of Envelope SB plugin ↔ CAMARA ↔ aeriOS
**Vasilis Pitsilis** | [vpitsilis@iit.demokritos.gr](mailto:vpitsilis@iit.demokritos.gr)
**Andreas Sakellaropoulos** | [asakellaropoulos@iit.demokritos.gr](mailto:asakellaropoulos@iit.demokritos.gr)

---


## 🤝 Contributors

The following contributors supported the work through reviews, validation, testing, integration activities, or technical discussions:
- Harilaos Koumaras | [koumaras@iit.demokritos.gr](mailto:koumaras@iit.demokritos.gr)
- Alex Kakyris | [akakyris@fogus.gr](mailto:akakyris@fogus.gr)
- Christos Milarokostas | [milarokostas@fogus.gr](mailto:milarokostas@fogus.gr)
- Dimitrios Uzunidis |  [duzinidis@iit.demokritos.gr](mailto:duzunidis@iit.demokritos.gr)
- Jason Diakoumakos |  [i.diakoumakos@oteresearch.gr](mailto:i.diakoumakos@oteresearch.gr)


---

## 📬 Technical Contact & Clarifications

For technical clarifications or questions related to the implementation details, architectural decisions, or the SB plugin ↔ CAMARA ↔ aerOS integration logic, please contact:

**Vasilis Pitsilis**  
[vpitsilis@iit.demokritos.gr](mailto:vpitsilis@iit.demokritos.gr)

---

## 📄 License

This project is licensed under the **STILL_TO_BE_DEFINED**