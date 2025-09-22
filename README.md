# 📡 Southbound Plugin API – CAMARA Integration for Athens Site Continuum

This project implements **Southbound Plugin** using [FastAPI](https://fastapi.tiangolo.com/) to provide service deployment and LCM over  Athens site (aerOS based) continuum.The onboarding and management of the applications on the **Athens Site Continuum** is abstracted through CAMARA APIs.

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
CAMARA_ENDPOINT_URL=https://athens-camara-endpoint.com
EAAS_APPLICATION_REPO_URL=https://athens-eaas-repo.com
DEBUG=true
LOG_FILE=.log/southbound.log
```

These values are accessed through a centralized `Settings` class (using `pydantic-settings`) and injected where needed.

---

## 🧩 API Capabilities

| Endpoint                            | Purpose                                   |
| ----------------------------------- | ----------------------------------------- |
| `POST /application_onboarding`      | Onboard a new application                 |
| `POST /create_application_instance` | Start an instance of an onboarded app     |
| `POST /stop_application_instance`   | Stop a running application instance       |
| `GET /{instanceId}/state/ws`        | Get current status of a specific instance |
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
version: '3.9'

services:
  southbound-api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - .:/app
```

### Run the app with Docker:

```bash
docker-compose up --build
```

Open your browser at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠 Development Notes

* 🧠 The CAMARA and EaaS clients are wrapped with `httpx` and managed via FastAPI dependencies.
* ⚙️ Shared configuration is accessed using a singleton `Settings` class from `app.config`.
* 🔁 `httpx.Client` is cached using `functools.lru_cache()` for connection reuse and performance.
* 🧪 Application logic is split between `routers`, `models`, and `api_clients` for maintainability.

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

## 🤝 Authors

- [vpitsilis@iit.demokritos.gr](mailto:vpitsilis@iit.demokritos.gr)
- [akakyris@fogus.gr](mailto:akakyris@fogus.gr)
- [milarokostas@fogus.gr](mailto:milarokostas@fogus.gr)
... more should follow


---


## 📔 What is needed now
Code handling application onboarding needs to be fixed.
 * Receive AppPkgInfo (this is done)
 * Query AppDescriptor from Application repository (this is included)
 * If needed retrieve application artifact (Not done, do we need this?)
 * Parse AppPkgInfo & AppDescriptor & any artifact (Draft done, work is needed)
 * Map to CAMARA AppManifest (Draft done, work is needed)

Code skeleton is there
* All models in pydantic and included
* CAMAR API calls included
* EaaS Application Repository calls included
* Initial parsing of EaaS objects to CAMARA done

We miss
* Careful parsing of objects and
* Proper mapping to CAMARA AppManifest
* Maybe to check all exceptions are handled ok. 

---

## 📄 License

This project is licensed under the **LATER_CHECK_FOR_LICENSE**.
