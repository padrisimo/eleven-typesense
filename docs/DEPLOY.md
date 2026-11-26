# Deploy runbook — GCP VM + Docker Compose

This runbook describes two paths. The **executed trial deployment** below was actually created and verified on 2026-11-26 with the €300 trial credit. The free-tier path after it is the $0-within-quotas recipe and was not executed.

## Executed trial deployment (200k sounds, GCS, embeddings)

Resources created in project `<PROJECT_ID>` (display name *Soundseek Trial*) on billing account `<BILLING_ACCOUNT_ID>`:

| Resource | Value |
|---|---|
| VM | `soundseek-trial`, `us-central1-a`, `e2-standard-2` (2 vCPU / 8 GiB), 50 GB `pd-balanced`, Debian 12 |
| Service account | `<SA_EMAIL>` |
| IAM | SA has `roles/storage.objectAdmin` on the bucket and `roles/iam.serviceAccountTokenCreator` on itself for V4 `signBlob` |
| Bucket | `gs://<BUCKET_NAME>`, `us-central1`, uniform bucket-level access |
| Firewall | `allow-soundseek-trial-web` (80/443), `allow-soundseek-trial-ssh` (22 from the operator IP only) |
| Budget | 50 EUR, filtered to the project, alerts at 50/90/100 % (`<BUDGET_ID>`) |
| DNS | `<VM_IP>.sslip.io`, real Let's Encrypt certificate issued by Caddy |

`gcloud` on the operator machine is pinned to the uv-managed Python 3.12 via `CLOUDSDK_PYTHON`. The GitHub repository is private, so the source was copied with a tarball and `gcloud compute scp`; only the built `ui/dist` was copied separately. Debian 12 has no `docker-compose-plugin` package, so Compose v5.8.0 was installed as a standalone CLI plugin under `/usr/local/lib/docker/cli-plugins`.

Key steps:

```bash
gcloud services enable compute.googleapis.com iamcredentials.googleapis.com \
  storage.googleapis.com billingbudgets.googleapis.com
gcloud billing budgets create --billing-account=<BILLING_ACCOUNT_ID> \
  --display-name="Soundseek trial (50 EUR)" --budget-amount=50EUR \
  --filter-projects=projects/<PROJECT_ID> \
  --threshold-rule=percent=0.50 --threshold-rule=percent=0.90 \
  --threshold-rule=percent=1.00
gcloud iam service-accounts create soundseek-app --display-name="Soundseek app (trial)"
gcloud storage buckets create gs://<BUCKET_NAME> \
  --location=us-central1 --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding gs://<BUCKET_NAME> \
  --member=serviceAccount:<SA_EMAIL> \
  --role=roles/storage.objectAdmin
gcloud iam service-accounts add-iam-policy-binding \
  <SA_EMAIL> \
  --member=serviceAccount:<SA_EMAIL> \
  --role=roles/iam.serviceAccountTokenCreator
gcloud compute instances create soundseek-trial --zone=us-central1-a \
  --machine-type=e2-standard-2 --boot-disk-size=50GB --boot-disk-type=pd-balanced \
  --image-family=debian-12 --image-project=debian-cloud \
  --service-account=<SA_EMAIL> \
  --scopes=https://www.googleapis.com/auth/cloud-platform --tags=soundseek-trial
```

On the VM, `.env` uses `STORAGE_BACKEND=gcs`, `GCS_BUCKET`, `GCS_PROJECT_ID`, `GCS_SIGNER_SERVICE_ACCOUNT`, `GENERATOR=mock`, `GUNICORN_WORKERS=2`, `DOMAIN=<VM_IP>.sslip.io`. Then:

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T api \
  python /db/seed.py --dsn "$DSN" --count 200000
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T api \
  python /scripts/reindex.py --dsn "$DSN" --collection sounds_v2 \
  --with-embeddings --limit 10000 --set-alias
```

Verified from the public HTTPS endpoint: `/health` and `/api/health` return `{"status":"ok","database":"connected"}`, `/` serves `<title>Soundseek</title>`, `q=door` returns 833 hits in 7 ms, `mode=hybrid` with `heavy metallic door sound` returns 586 hits in 19 ms, two identical `/generate` calls return the same `sound_id` with `idempotent: true` on the second, the GCS signed preview URL returns **200 audio/mpeg** (17,180 bytes), `/download` returns **403** without `X-Subscriber: true`, and the generated sound is searchable. Full numbers are in `docs/PERFORMANCE.md`.

### Trial teardown (irreversible)

Stop the VM when not in use; delete everything before the trial credit expires on 2026-02-25 or the account starts charging.

```bash
export PROJECT_ID=<PROJECT_ID>
gcloud compute instances stop soundseek-trial --zone=us-central1-a
gcloud compute instances delete soundseek-trial --zone=us-central1-a --quiet
gcloud compute firewall-rules delete allow-soundseek-trial-web allow-soundseek-trial-ssh --quiet
gcloud storage rm -r gs://<BUCKET_NAME>
gcloud iam service-accounts delete \
  <SA_EMAIL> --quiet
gcloud billing budgets delete <BUDGET_ID> \
  --billing-account=<BILLING_ACCOUNT_ID> --quiet
gcloud projects delete "$PROJECT_ID" --quiet
```

## Free-tier demo path ($0 within quotas)

Google's Free Program still requires a billing account, but the following fits its published limits: **one non-preemptible e2-micro per month** in `us-west1`, `us-central1` or `us-east1`, **30 GB-months** of standard persistent disk and **1 GB** of North America egress. Cloud Storage gives 5 GB-months in US regions. Cloud Run has a free tier, but it does not include Postgres or Typesense, so it does not remove the need for a VM here.

This path uses **local audio storage**, 10,000 seeded sounds, one gunicorn worker, no embeddings and a free `sslip.io` hostname instead of a purchased domain. The standard paid path below remains the full 200k setup.

### 1. Variables and APIs

```bash
export PROJECT_ID=my-gcp-project
export REGION=us-central1
export ZONE=us-central1-a
export VM_NAME=soundseek-free
export SA_NAME=soundseek-free-app
export SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
export MY_IP=$(curl -s https://ifconfig.me)

gcloud config set project "$PROJECT_ID"
gcloud services enable compute.googleapis.com
```

### 2. Service account and VM

```bash
gcloud iam service-accounts create "$SA_NAME" --display-name="Soundseek free demo"

gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type=e2-micro \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --service-account="$SA_EMAIL" \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=soundseek-free

gcloud compute firewall-rules create allow-soundseek-free-web \
  --network=default --allow=tcp:80,tcp:443 --target-tags=soundseek-free

gcloud compute firewall-rules create allow-soundseek-free-ssh \
  --network=default --allow=tcp:22 --source-ranges="$MY_IP/32" --target-tags=soundseek-free
```

Get the public IP and derive the hostname. `sslip.io` resolves `<ip>.sslip.io` to that IP; its own documentation cites Caddy + Let's Encrypt HTTP-01 as a supported example.

```bash
export EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)')
export DOMAIN="$EXTERNAL_IP.sslip.io"
echo "$DOMAIN"
```

### 3. Build and copy the UI, then deploy

Build the UI locally because the VM has no Node 22 installed:

```bash
(cd ui && npm install && npm run build)
gcloud compute scp --recurse ui/dist "$VM_NAME":~/soundseek-dist --zone="$ZONE"
```

SSH into the VM:

```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"
```

Inside the VM:

```bash
sudo apt-get update
sudo apt-get install -y git curl docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker

git clone https://github.com/padrisimo/eleven-typesense.git
cd eleven-typesense
mkdir -p ui && cp -r ~/soundseek-dist ui/dist

cat > .env <<EOF
POSTGRES_PASSWORD=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 24)
TYPESENSE_API_KEY=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 24)
LOCAL_SIGNING_SECRET=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 24)
STORAGE_BACKEND=local
GENERATOR=mock
GUNICORN_WORKERS=1
DOMAIN=$DOMAIN
CADDY_EMAIL=admin@$DOMAIN
EOF

set -a; . ./.env; set +a
DC="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
DSN="postgresql://soundsnap:${POSTGRES_PASSWORD}@db:5432/soundsnap"

$DC up -d --build
$DC exec api python /db/seed.py --dsn "$DSN" --count 10000
$DC exec api python /scripts/reindex.py --dsn "$DSN" --set-alias

curl -fsS https://$DOMAIN/health
curl -fsS https://$DOMAIN/api/health
curl -fsS https://$DOMAIN/
```

Caddy serves the built UI at `/`, proxies `/api/*` to the API with the prefix stripped, and keeps `/health` for compatibility. Do not enable `--with-embeddings` on e2-micro: CPU inference is too slow for 1 GB of RAM.

### 4. Free-tier operations and teardown

```bash
# Stop the VM when not in use; free tier is counted by hours per month.
gcloud compute instances stop "$VM_NAME" --zone="$ZONE"
gcloud compute instances start "$VM_NAME" --zone="$ZONE"

# Irreversible: deletes the demo VM, rules and service account.
gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --quiet
gcloud compute firewall-rules delete allow-soundseek-free-web allow-soundseek-free-ssh --quiet
gcloud iam service-accounts delete "$SA_EMAIL" --quiet
```

If you later add the optional GCS bucket, create it in `us-central1` with `--uniform-bucket-level-access` and add it to the teardown block.

## Standard production path (paid)

### 0. Local variables

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

git clone https://github.com/padrisimo/eleven-typesense.git
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
