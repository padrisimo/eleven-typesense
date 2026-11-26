# Deploy runbook — GCP VM + Docker Compose

This is a runbook, not an executed deployment. No `gcloud` command was run while building this project. Estimated cost is a single small VM plus a regional bucket; stop or tear down when finished.

## 0. Local variables

Run these in your shell and keep them for the teardown block:

```bash
export PROJECT_ID=my-gcp-project
export REGION=europe-west1
export ZONE=europe-west1-b
export VM_NAME=soundseek
export BUCKET=my-soundseek-audio
export SA_NAME=soundseek-app
export SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
export DOMAIN=soundseek.example.com
export MY_IP=$(curl -s https://ifconfig.me)

gcloud config set project "$PROJECT_ID"
gcloud services enable compute.googleapis.com iamcredentials.googleapis.com storage.googleapis.com
```

## 1. Bucket and least-privilege service account

The VM has no JSON key on disk. It uses its attached service account via Application Default Credentials; signing GCS V4 URLs uses IAM `signBlob`, which needs `iam.serviceAccounts.signBlob` on that same account.

```bash
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access

gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Soundseek app"

gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SA_EMAIL" \
  --role=roles/storage.objectAdmin

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="serviceAccount:$SA_EMAIL" \
  --role=roles/iam.serviceAccountTokenCreator
```

`roles/storage.objectAdmin` is limited to the one bucket; the token-creator role is limited to the app service account itself.

## 2. VM and firewall

```bash
gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type=e2-standard-2 \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-balanced \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --service-account="$SA_EMAIL" \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=soundseek

gcloud compute firewall-rules create allow-soundseek-web \
  --network=default \
  --allow=tcp:80,tcp:443 \
  --target-tags=soundseek

gcloud compute firewall-rules create allow-soundseek-ssh \
  --network=default \
  --allow=tcp:22 \
  --source-ranges="$MY_IP/32" \
  --target-tags=soundseek
```

Caddy needs port 80 for the ACME HTTP-01 challenge and redirects it to HTTPS. SSH is restricted to your IP.

## 3. Deploy on the VM

```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"
```

Inside the VM:

```bash
sudo apt-get update
sudo apt-get install -y git curl docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker

git clone https://github.com/<your-org>/eleven-typesense.git
cd eleven-typesense
cp .env.example .env
```

Edit `.env` at minimum:

```dotenv
POSTGRES_PASSWORD=<random-alphanumeric>
TYPESENSE_API_KEY=<random-string>
LOCAL_SIGNING_SECRET=<random-string>
STORAGE_BACKEND=gcs
GCS_BUCKET=my-soundseek-audio
GCS_PROJECT_ID=my-gcp-project
GCS_SIGNER_SERVICE_ACCOUNT=soundseek-app@my-gcp-project.iam.gserviceaccount.com
DOMAIN=soundseek.example.com
CADDY_EMAIL=admin@example.com
GENERATOR=mock
ELEVENLABS_API_KEY=
```

Point `DOMAIN` at the VM's external IP with an A record **before** starting Caddy, otherwise ACME cannot issue a certificate. Set `GENERATOR=elevenlabs` and the API key only if sound-effect generation is enabled on the plan; otherwise keep the mock.

```bash
set -a; . ./.env; set +a   # export .env for the DSN below
DC="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
DSN="postgresql://soundsnap:${POSTGRES_PASSWORD}@db:5432/soundsnap"

$DC up -d --build
$DC exec api python /db/seed.py --dsn "$DSN"
$DC exec api python /scripts/reindex.py --dsn "$DSN" --set-alias

# Optional: semantic index (CPU inference is slow, hence the limit)
$DC exec api python /scripts/reindex.py --collection sounds_v2 --with-embeddings --limit 10000 --dsn "$DSN"
$DC exec api python /scripts/reindex.py --collection sounds_v2 --only-alias

curl -fsS https://$DOMAIN/health
```

Only Caddy publishes ports: `80`, `443` and `443/udp`. Postgres, Typesense and the API are reachable inside the `backend`/`edge` networks only. The `api` service mounts `./db` and `./scripts` read-only in production so the maintenance commands above work.

## 4. Operations

```bash
# Repair sounds that failed to index (indexed_at IS NULL)
$DC exec api python /scripts/reindex.py --only-unindexed --dsn "$DSN"

# Logical backup (VM disk snapshots are a separate mechanism)
$DC exec -T db pg_dump -U soundsnap -Fc soundsnap > "soundseek-$(date +%F).dump"

# Roll back a bad alias switch
$DC exec api python /scripts/reindex.py --collection sounds_v1 --only-alias
```

There is no point-in-time recovery on a self-managed VM: logical dumps and disk snapshots are your only recovery path. Managed Cloud SQL would give PITR and automated backups.

## 5. Teardown — deletes everything, including data

```bash
gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --quiet
gcloud compute firewall-rules delete allow-soundseek-web allow-soundseek-ssh --quiet
gcloud storage rm -r "gs://$BUCKET"
gcloud iam service-accounts delete "$SA_EMAIL" --quiet
```

Review the names printed above before running this block; it is irreversible.
