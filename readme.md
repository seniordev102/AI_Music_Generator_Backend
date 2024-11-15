### how to run the project(BACKEND API)

first intall the requirements using pip

```bash
pip3 install -r requirements.txt
```

configer the .env file based on the provided .env.example file

```bash
cp .env.example .env
```

run the project

```bash
python3 server.py
```

## how to run the migration

```bash
alembic revision --autogenerate -m "<your message>"
alembic upgrade head
```

### sample ipfs nft json format

```json
{
  "dna": "9aa6bad0-bf90-4a9e-9093-46f4749562e2",
  "name": "_1_Eagle_Spirit_639HZ",
  "description": "The Eagle card symbolizes divine connection and vision. Eagles soar to great heights. Embrace your spiritual connection and trust in your intuition to guide you toward enlightenment.",
  "image": "ipfs://QmUjVtNkCbxBswWtEpVaLubjn2fy5ywixv1azjdfkR5u4v/images/1.png",
  "attributes": [],
  "mp3": "ipfs://QmUjVtNkCbxBswWtEpVaLubjn2fy5ywixv1azjdfkR5u4v/mp3/1.mp3",
  "hires_audio": "ipfs://QmUjVtNkCbxBswWtEpVaLubjn2fy5ywixv1azjdfkR5u4v/hi-res-audio/1.wav",
  "author": "IAH.FIT"
}
```

### pinata keys

```bash
API Key: 8c883eced5a7518a26f1
API Secret: 85ecf0527e720603a6a4ee7d22b5315ba62ab25ee62b55708fdcef9c9ad82b78
JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiI4MWMyY2RhOC03OWUxLTRmNWQtODcyNi04MjgyOTFjMDdhMWQiLCJlbWFpbCI6Im1pY2hhZWxAaWFoLmZpdCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaW5fcG9saWN5Ijp7InJlZ2lvbnMiOlt7ImlkIjoiRlJBMSIsImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxfSx7ImlkIjoiTllDMSIsImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxfV0sInZlcnNpb24iOjF9LCJtZmFfZW5hYmxlZCI6ZmFsc2UsInN0YXR1cyI6IkFDVElWRSJ9LCJhdXRoZW50aWNhdGlvblR5cGUiOiJzY29wZWRLZXkiLCJzY29wZWRLZXlLZXkiOiI4Yzg4M2VjZWQ1YTc1MThhMjZmMSIsInNjb3BlZEtleVNlY3JldCI6Ijg1ZWNmMDUyN2U3MjA2MDNhNmE0ZWU3ZDIyYjUzMTViYTYyYWIyNWVlNjJiNTU3MDhmZGNlZjljOWFkODJiNzgiLCJpYXQiOjE2OTQxOTkxNDF9.RIfIUnJmKqGSSkdS-ajcZoMC_yPEbRphOpwEXN26_EE
```

stripe integaration
first create the subscription product using cli or curl
stripe prices create --unit-amount 599 --currency usd -d "recurring[interval]=month" -d "product_data[name]=premium" --lookup-key premium
here 599 = 5.99
stripe prices create --unit-amount 1499 --currency usd -d "recurring[interval]=month" -d "product_data[name]=commercial" --lookup-key commercial

```bash
curl https://api.stripe.com/v1/prices \
  -u sk_test_xxx: \
  -d "unit_amount"=599 \
  -d "currency"=usd \
  -d "recurring[interval]"=month \
  -d "product_data[name]"=premium \
  -d "lookup_key"=premium \
```

stripe listen --forward-to localhost:8800/api/v1/subscription/stripe/webhook
