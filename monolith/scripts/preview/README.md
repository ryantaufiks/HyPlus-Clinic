# Screen previews for the platform page

The gallery on `/` shows real screens with fictional data. To refresh them after a UI change:

1. Start a throwaway demo instance on port 8011 with the fictional data (never use the production database):

       docker run -d --name aivin-demo -u 0 -p 127.0.0.1:8011:8000 --env-file .env \
         -e DEBUG=true -e POSTGRES_DB= -e SECURE_SSL_REDIRECT=false -e PUBLIC_BASE_URL= -e REDIRECT_HOSTS= \
         -v "$PWD/scripts/preview:/demo" --entrypoint sh aivin-web:latest -c \
         "python manage.py migrate -v0 && python manage.py createcachetable && python manage.py shell < /demo/seed_demo.py && python manage.py runserver 0.0.0.0:8000"

   `docker logs aivin-demo` prints the in-progress visit id, a waiting ticket token and the portal patient.

2. Capture with headless Chrome (Node 22, no packages needed):

       GATEWAY_TOKEN=... OUT=/tmp/shots/ node scripts/preview/capture.mjs <visit id> <ticket token> <portal Patient ID>

3. Convert the PNGs to WebP into `static/img/preview/` (1440 px wide, phones 600 px, plus 360 px `-thumb` versions), then remove the demo container.
