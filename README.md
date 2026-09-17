# MatraCare

A maternity guide prototype with a JavaScript frontend on Netlify and a Python LangChain backend on Vercel. LangChain's `ChatOpenAI` uses the OpenAI client internally with your Groq key and Groq's endpoint. No OpenAI key is needed.

The LLM workflow is `ChatPromptTemplate -> ChatOpenAI -> StrOutputParser`. Vercel's standard Python HTTP handlers expose it to the frontend, with no FastAPI dependency. `backend/app.py` contains the chain and validation; `backend/api/` contains the function entrypoints.

Start with [Local development](#local-development) to test the full website. For publishing, follow [Deploy the backend first](#deploy-the-backend-first), [Connect the frontend](#connect-the-frontend), then [Update your existing Netlify site](#update-your-existing-netlify-site).

## Setup reference

| Setting | Local testing | Production |
| --- | --- | --- |
| Website | `http://localhost:8080` | Your existing Netlify URL |
| Backend origin | `http://localhost:8001` | Your Vercel production URL |
| Health check | `GET http://localhost:8001/health` | `GET https://your-backend.vercel.app/health` |
| Question endpoint | `POST http://localhost:8001/api/ask` | `POST https://your-backend.vercel.app/api/ask` |
| `config.js` / `apiBaseUrl` | Empty string | Vercel origin, without `/api/ask` |
| Groq key | `backend/.env` | Vercel environment variables |
| Python entrypoint | `backend/dev.py` | `backend/api/ask.py` and `backend/api/health.py` |

Prerequisites: Python 3.10+ locally (the existing environment uses 3.11), Node.js 18+ for the frontend build, and a Groq API key. Production uses Python 3.12 from `backend/.python-version`. Deployment also requires Vercel and Netlify accounts; GitHub is optional if using Vercel CLI and manual Netlify uploads.

The frontend server serves files from `dist/`; JavaScript runs in your browser. The browser sends JSON to Python, and Python calls the model hosted by Groq. No model runs on your Mac. `GET /health` only checks configuration; **Test LLM** makes a real provider call.

## Deploy the backend first

1. Upload this project to a private GitHub repository, or use the CLI alternative below. Keep `backend/` as a subfolder of the repository. Never commit real API keys or `.env` files; `.gitignore` excludes them. Confirm the repository contains `backend/requirements.txt`, `backend/vercel.json`, and `backend/api/`.
2. In Vercel, choose **Add New > Project** and import the repository.
3. Set **Root Directory** to `backend` and **Framework Preset** to **Other**. Leave build command and output directory unset. Vercel detects the Python functions under `api/`; `vercel.json` configures the health alias and function timeout. `.python-version` selects Python 3.12. If updating an existing FastAPI project, remove its old framework/build overrides.
4. Set the following Vercel environment variables for Production (and Preview if you plan to test preview deployments):

| Variable | Value |
| --- | --- |
| `GROQ_API_KEY` | Your existing Groq key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `ALLOWED_ORIGINS` | `https://fantastic-youtiao-51e03c.netlify.app` |

Use your actual Netlify origin if you have renamed the site. Multiple origins are comma-separated, without paths. The model is controlled by the backend, not visitors.

5. Deploy and copy the stable production URL, such as `https://your-backend.vercel.app`. Avoid temporary preview/deployment URLs.
6. Open `/health` on that URL. Expect `{"status":"ok","provider":"groq","configured":true}`. This confirms configuration but does not call Groq.
7. Verify a real Groq response with the command below (replace the example hostname). There is no FastAPI `/docs` page now.
8. Ensure the production API is accessible without a Vercel login. If Deployment Protection protects production, adjust it for this API project. Never embed bypass secrets in frontend code.

Test the production API (replace the example hostname):

```bash
curl https://your-backend.vercel.app/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Reply with: ready"}'
```

### Vercel CLI alternative without Git

From your project folder:

```bash
npm install -g vercel
cd backend
vercel login
vercel
```

Follow the prompts to create or link your backend project. The current directory is already `backend`, so use `.` as the code directory, not another nested `backend`. Use the Other framework preset with no custom build command or output directory. The initial deployment is a preview and may be protected or lack your production key.

In that Vercel project's settings, add the Production environment variables from the table above. Then, still in `backend/`, run:

```bash
vercel --prod
```

Use the stable production URL shown for the project and run the health and Groq checks above. Return to the repository root with `cd ..` before running frontend build commands. You do not run `dev.py` on Vercel; Vercel starts the handlers for incoming requests.

## Connect the frontend

Set your Vercel production origin in root `config.js`:

```javascript
window.MATRACARE_CONFIG = {
  apiBaseUrl: "https://your-backend.vercel.app"
};
```

Do not append `/api/ask`. This address is public; API keys belong only in Vercel environment variables. The deployed frontend reports an unconfigured service until this URL is set.

## Update your existing Netlify site

Deploy Vercel and verify it BEFORE updating Netlify. If using automatic Git deployment, pause Netlify auto-publishing while preparing the migration, then resume once the backend URL is configured. Local edits do not change your live site.

Use the EXISTING Netlify project for `https://fantastic-youtiao-51e03c.netlify.app`. Do not create a new Netlify project or rename it. Updating its deployment keeps its current URL.

### Manual folder upload

1. From the repository root, run the following with Node.js 18 or later:

```bash
node scripts/build-frontend.mjs
```

2. Open your existing Netlify project's **Deploys** page.
3. Upload the generated `dist/` folder in that site's manual deploy area. Upload only `dist/`, not the source repository.
4. Open your existing website URL and click **Test LLM**.

### Git deployment

1. Connect this repository to the existing Netlify project, or push to its already linked repository.
2. Use the repository root as the base directory, build command `node scripts/build-frontend.mjs`, and publish directory `dist`. These settings are in `netlify.toml`.
3. Remove any old dashboard Functions directory override (`netlify/functions`). There is no Netlify backend now.
4. Deploy after `config.js` contains the working Vercel URL.

After verifying a non-urgent question and **Test LLM**, remove obsolete Groq variables from Netlify. Keep them on Vercel. Urgent questions use local guidance, so they do not test API connectivity. Vercel environment changes require a redeploy.

### Verify the complete deployment

1. Open the Vercel `/health` URL and confirm `configured` is `true`.
2. Send the test `POST /api/ask` request above and confirm it returns an answer.
3. Open your existing Netlify URL, refresh, and click **Test LLM**. Then submit a non-urgent question.
4. In browser Developer Tools > Network, check that the `ask` request goes to your Vercel origin, not localhost. If curl succeeds but the browser fails, check CORS and Deployment Protection.
5. Stop local servers and reload the deployed Netlify site. It should still answer through Vercel and Groq. Local Python processes are not required in production.

For a renamed Netlify site, custom domain, or preview frontend, add that exact origin to Vercel's `ALLOWED_ORIGINS` and redeploy. Only add localhost there if you deliberately want a local frontend to call the production backend.

## Local development

### Terminal 1: activate the environment and start the backend

The LangChain environment already exists on this Mac at:

```text
/Users/srijaydeshpande/Desktop/Srijay/codes/maternity_help/backend/.venv-langchain
```

It uses Python 3.11.15. Do not recreate it or use the older `backend/.venv` environment. In your zsh terminal, run:

```bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity_help
source backend/.venv-langchain/bin/activate
command -v python
python --version

cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity_help
source backend/.venv-langchain/bin/activate
python backend/dev.py
```

The Python path should end in `backend/.venv-langchain/bin/python`. Your prompt will usually show `(.venv-langchain)`. Activation applies only to this terminal; repeat it in a new backend terminal.

Install dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Open `backend/.env` in your editor. This file has already been created on this Mac. Set the key there:

```dotenv
GROQ_API_KEY=your_actual_groq_key
GROQ_MODEL=openai/gpt-oss-120b
ALLOWED_ORIGINS=https://fantastic-youtiao-51e03c.netlify.app,http://localhost:8080,http://127.0.0.1:8080
```

The backend automatically loads this exact file, regardless of your terminal's working directory. Do not put the key in `config.js`, `app.js`, or HTML. `.gitignore` and `.vercelignore` exclude `.env`; the Netlify build copies only public frontend files. On a fresh clone, create `backend/.env` using `backend/.env.example` as a template.

Existing environment variables take precedence over `.env`. If you previously exported these settings in this terminal, run `unset GROQ_API_KEY GROQ_MODEL ALLOWED_ORIGINS` once so the file's values are used. For production, keep setting the key in Vercel's environment-variable settings; do not upload `.env`.

Start the backend from the same activated terminal:

```bash
python backend/dev.py
```

Keep this terminal open. Visit `http://localhost:8001/health`; `configured: true` means the key is present, but does not verify it with Groq. Restart the backend whenever you change `.env`. If port 8001 is occupied, stop the existing backend with Ctrl+C in its terminal, then start this one.

The backend is an API, not the website. Opening `http://localhost:8001/` returns `Method not allowed` because there is no homepage there. Open `/health` to check the backend, or the frontend on port 8080 to use the website.

### Terminal 2: test Groq and start the frontend

This terminal does not need virtual-environment activation. First test a real Groq call:

```bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity_help
curl http://localhost:8001/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Reply with: ready"}'
```

Expect JSON containing `answer` and `model`. For local testing, set `apiBaseUrl` to an empty string in `config.js`:

```javascript
window.MATRACARE_CONFIG = {
  apiBaseUrl: ""
};
```

Build and serve the frontend:

```bash
node scripts/build-frontend.mjs
python3 -m http.server 8080 --bind 127.0.0.1 --directory dist
```

Visit `http://localhost:8080`, click **Test LLM**, then submit a non-urgent question. Urgent questions use local guidance and do not verify Groq connectivity. If the frontend already runs on port 8080, rebuild and refresh that preview instead of starting a second server.

A blank `apiBaseUrl` uses `http://localhost:8001` on localhost only. Restore the production Vercel URL before deployment. After frontend edits, rerun `node scripts/build-frontend.mjs` and refresh the browser. Local browser origins are allowed by default; if you override `ALLOWED_ORIGINS`, include `http://localhost:8080`. If you change the backend port again, update the local default in `app.js` too and rebuild.

### Automated tests and stopping

In a separate terminal, run tests without a real key or API charges:

```bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity_help
source backend/.venv-langchain/bin/activate
cd backend
python -m unittest discover -s tests -v
```

Stop each server with Ctrl+C in its terminal. Then run `deactivate` to leave an activated environment. Your key remains in `backend/.env` for the next run.

On another machine, create the environment first with `python3.11 -m venv backend/.venv-langchain` (or use an installed Python 3.10+ interpreter). Vercel uses Python 3.12.

### Address already in use or no visible terminal

A preview started by the coding assistant can keep running as a background process even if you did not open a second terminal. Do not start a duplicate server. On macOS, inspect the listeners:

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8001 -sTCP:LISTEN
```

If port 8080 is already serving this project's `dist/`, open `http://localhost:8080` and reuse it. Rebuild the frontend after edits and refresh. If a backend is already running, check `/health`; restart it after changing Python files or `.env` because `dev.py` does not auto-reload.

To take control of a background preview, identify its PID from `lsof` and inspect it with `ps -p PID -o command=` (replace `PID` with the number). Only after confirming it is your project server, stop it with `kill PID`, then start the documented server command in your own terminal. Do not stop unrelated processes. No fixed PID is recorded here because process IDs change.

If you choose a different frontend port, add its origin to `ALLOWED_ORIGINS` in `backend/.env` and restart Python. If you change the backend port, update `dev.py` and the local URL in `app.js`, then rebuild `dist/`.

## Troubleshooting

- Connection/CORS error: verify `config.js`, production Deployment Protection, and the exact website origin in `ALLOWED_ORIGINS`. Redeploy after changes.
- Health works but answers fail: check the Groq key, model, and quota. Health does not validate the key with Groq.
- Model unavailable: use a model enabled for your Groq account, update `GROQ_MODEL` in `backend/.env`, and restart the backend. The `openai/gpt-oss-120b` model here runs through Groq with your Groq key, not OpenAI's API.
- HTML or 404 instead of JSON: verify the Vercel root is `backend` and try `/health` directly.
- 429: Groq rate limit. Wait or adjust provider quota.
- Timeout: backend Groq timeout is 25 seconds; frontend deadline is 35 seconds.
- Changes not visible: rebuild `dist/` after frontend edits and refresh the browser. Restart `dev.py` after backend or `.env` edits. Redeploy the appropriate service for production changes.
- Local API works but deployed site fails: restore the Vercel URL in `config.js`, rebuild, and redeploy Netlify. An empty URL only has a localhost default; it does not configure production.

Netlify publishes only frontend assets through `scripts/build-frontend.mjs`. The backend API is public: CORS restricts browsers, not callers using scripts. Authentication and shared rate limiting would be additional work before wider public use.

## Medical Safety

This remains an educational prototype. The existing prompt and keyword checks are retained, with bleeding checked on the server as it already was in the browser. These checks are not clinically validated triage. PubMed retrieval is not implemented by this migration.

## References

- [Python functions on Vercel](https://vercel.com/docs/functions/runtimes/python)
- [Creating Netlify deployments](https://docs.netlify.com/deploy/create-deploys/)
- [LangChain ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [Groq OpenAI client compatibility](https://console.groq.com/docs/openai)
- [Vercel Hobby fair-use rules](https://vercel.com/docs/limits/fair-use-guidelines): free hosting is for personal, non-commercial use within quotas. Groq usage is separate.
# maternity
