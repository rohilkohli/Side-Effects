# Deploy from Cloud Shell (about 10 minutes)

No API key is needed: on Cloud Run the app calls Gemini through Vertex AI using its own service account.

1. Open https://console.cloud.google.com, pick (or create) a project with billing turned on, and click the Cloud Shell icon (top right, `>_`).
2. In Cloud Shell, click the three-dot menu, then **Upload**, and upload `side-effects-app.zip`.
3. Run:

   ```bash
   unzip -q side-effects-app.zip && cd side-effects-app
   PROJECT_ID=$(gcloud config get-value project) bash deploy.sh
   ```

   Answer `y` if it asks to create an Artifact Registry repository. When it finishes it prints a `Service URL` ending in `.run.app`. That is the prototype link for the submission.
4. Open the link, pick Maya, press **Run both agents live**, and check both lanes finish.

## If something fails

| Message | Fix |
|---|---|
| `allUsers` / "organization policy" error on `--allow-unauthenticated` | The project belongs to an organisation that blocks public services. Use a personal project with billing instead. |
| Agent lane shows `Gemini refused the request (404)` and a model name | That model is not available to the project yet. Redeploy with another one: `PROJECT_ID=$(gcloud config get-value project) GEMINI_MODEL=<model id from the Vertex AI Model Garden> bash deploy.sh` |
| `Gemini refused the request (429)` | Quota. Wait a minute and rerun; for judging, request a quota increase in the console under IAM & Admin, Quotas. |
| Billing not enabled | Link a billing account to the project, then rerun the same command. |

## Keeping it live through judging

The service scales to zero when idle (no cost) and wakes on the first request, so the first page load after a quiet spell takes a few seconds. Leave the project and billing account active until results are announced.

Never paste an API key into the repo, the deck or the video. This deploy path uses none.
