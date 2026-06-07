# 🐳 OLLIE Docker Deployment

Dieses Setup verwendet vorkonfigurierte Images aus der GitHub Container Registry und ist ideal für Endnutzer.

## 🚀 Schnellstart

1. **`docker-compose.yml` erstellen:**
   Ersetze `<REPO_NAME>` durch den Repository-Pfad in Kleinbuchstaben (z. B. `hs-osnabrueck/ollie`).

   ```yaml
   services:
     backend:
       image: ghcr.io/<REPO_NAME>-backend:latest
       environment:
         - ROOT_PATH=/api
       volumes:
         - ./backend_data:/app/backend/data
         - ./chroma_db:/app/chroma_db

     frontend:
       image: ghcr.io/<REPO_NAME>-frontend:latest
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - caddy_data:/data
       depends_on:
         - backend

   volumes:
     caddy_data:
   ```

2. **Container starten:**
   ```bash
   docker compose up -d
   ```

3. **HTTPS vertrauen:**
   Öffne [https://localhost](https://localhost) und akzeptiere die Browser-Warnung (oder tippe `thisisunsafe`).

4. **Manifest:**
   Lade `manifest/manifest.docker.xml` in Outlook hoch.
