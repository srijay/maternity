# MatraCare

A maternity guide with a JavaScript frontend on Netlify and a Python LangChain backend on Vercel. LangChain's ChatOpenAI uses the OpenAI client with a Groq key and Groq's endpoint. The model runs on Groq, not on your Mac, and no OpenAI API key is required.

Instructions reviewed against the project configuration and hosting documentation on September 17, 2026.

## Project addresses

| Purpose | Address |
| --- | --- |
| Current project directory | /Users/srijaydeshpande/Desktop/Srijay/codes/maternity |
| Production backend | https://maternity-taupe.vercel.app |
| Production health check | https://maternity-taupe.vercel.app/health |
| Direct health function | https://maternity-taupe.vercel.app/api/health |
| Production question endpoint | POST https://maternity-taupe.vercel.app/api/ask |
| Existing frontend | https://fantastic-youtiao-51e03c.netlify.app |
| Local backend | http://localhost:8001 |
| Local frontend | http://localhost:8080 |
| Optional local frontend port | http://localhost:8082 |

The folder is now named **maternity**. All commands below use the new location. If your Netlify site has since been renamed, use its current origin wherever the old Netlify address appears.

Start with [Local testing](#local-testing). To publish, follow [Vercel deployment](#vercel-deployment), then [Netlify deployment](#netlify-deployment). Updating the existing Netlify project preserves its URL.

## How the project is connected

~~~text
Browser running app.js
    -> POST /api/ask on the Python backend
    -> input validation and urgent-symptom checks
    -> LangChain prompt -> ChatOpenAI -> text parser
    -> Groq
    -> JSON answer back to the browser
~~~

| File | Responsibility |
| --- | --- |
| index.html, styles.css, app.js, assets/ | Website UI and browser behavior |
| config.js | Backend address selection |
| scripts/build-frontend.mjs | Copies only public frontend files into dist/ |
| backend/dev.py | Local Python HTTP server on port 8001 |
| backend/http_api.py | JSON requests, responses, CORS, and HTTP methods |
| backend/app.py | Loads .env, validates questions, and calls the LangChain chain |
| backend/api/ask.py | Vercel entrypoint inheriting AskHandler |
| backend/api/health.py | Vercel entrypoint inheriting HealthHandler |
| backend/vercel.json | Vercel function settings and /health rewrite |
| backend/requirements.txt | Python dependencies |
| netlify.toml | Frontend build and publish settings |

The small Vercel entrypoints use inheritance: their classes contain "pass" because the implementation lives in the shared handlers. Locally, dev.py imports those shared handlers directly. On Vercel, the platform runs the functions; do not start dev.py there.

The frontend server only serves files. JavaScript runs in the browser and calls the backend directly. Different ports/domains require CORS permission. CORS is not authentication and does not prevent requests from scripts.

## Local testing

### 1. Activate the Python environment

Requirements: Python 3.10+ and Node.js 18+. This Mac's LangChain environment uses Python 3.11; Vercel is configured for Python 3.12.

Open Terminal 1 and enter the project directory:

~~~bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity
~~~

On this Mac, the environment already exists at the corrected location. Only for a fresh clone where it does not exist, create it first:

~~~bash
python3.11 -m venv backend/.venv-langchain
~~~

Then activate it and install dependencies:

~~~bash
source backend/.venv-langchain/bin/activate
command -v python
python --version
python -m pip install -r backend/requirements.txt
~~~

The Python path must end in **maternity/backend/.venv-langchain/bin/python**. Your prompt will usually show (.venv-langchain). Activation applies only to this terminal. Use .venv-langchain, not the older .venv environment.

Use an installed Python 3.10+ interpreter if python3.11 is unavailable. Node.js 18+ is sufficient for the frontend build script; use a currently supported Node.js LTS release for installing hosting CLIs. If you move the project again, virtual environments may retain absolute paths; recreate the environment at the new location rather than committing it to Git.

### 2. Put your Groq key in backend/.env

Open backend/.env in your editor. On a fresh clone, create it using backend/.env.example as a template. Keep these settings:

~~~dotenv
GROQ_API_KEY=your_actual_groq_key
GROQ_MODEL=openai/gpt-oss-120b
ALLOWED_ORIGINS=https://fantastic-youtiao-51e03c.netlify.app,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8082,http://127.0.0.1:8082
~~~

Replace only the key placeholder with your actual key. No terminal key entry is required.

The backend loads backend/.env at startup, independent of the working directory. Existing environment variables take precedence. If you previously exported these settings in Terminal 1, clear them once before starting:

~~~bash
unset GROQ_API_KEY GROQ_MODEL ALLOWED_ORIGINS
~~~

Never put the key in config.js, app.js, or HTML. .gitignore and .vercelignore exclude .env files; the frontend build publishes only an explicit list of public files. Production uses Vercel environment variables, not your local .env file.

### 3. Start the backend in Terminal 1

From the project root, with the environment activated:

~~~bash
python backend/dev.py
~~~

Keep this terminal running. Open http://localhost:8001/health. The expected response after adding your key is:

~~~json
{"status":"ok","provider":"groq","configured":true}
~~~

This confirms the key is present, not that Groq accepts it. The backend root http://localhost:8001/ is not a homepage and returns "Method not allowed". Restart the backend after editing Python files or .env; dev.py does not auto-reload.

### 4. Test an actual Groq call

Open Terminal 2:

~~~bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity
curl -i http://localhost:8001/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Reply with: ready"}'
~~~

Expect HTTP 200 and JSON with answer and model. This test calls Groq and uses provider quota. The model is hosted by Groq even though its name starts with openai/.

### 5. Build and start the frontend in Terminal 2

No virtual-environment activation is needed for this terminal.

~~~bash
node scripts/build-frontend.mjs
python3 -m http.server 8080 --bind 127.0.0.1 --directory dist
~~~

Open **http://localhost:8080**, click **Test LLM**, then submit a non-urgent question. Urgent questions use built-in guidance and do not verify Groq connectivity.

config.js detects localhost and leaves apiBaseUrl empty there; app.js then uses http://localhost:8001. When hosted on Netlify, the same configuration uses https://maternity-taupe.vercel.app. You do not need to switch configuration values between local testing and deployment.

After frontend edits, rebuild dist/ and refresh the browser. Do not edit generated files inside dist/ directly or open index.html with a file:// URL.

### 6. Optional: use frontend port 8082

Instead of starting the frontend on 8080, run:

~~~bash
python3 -m http.server 8082 --bind 127.0.0.1 --directory dist
~~~

Open **http://localhost:8082**. Keep the backend on 8001. Ensure the 8082 origins shown in the .env example above are present, then restart the backend. No frontend API URL change is required.

### 7. Address already in use and background servers

A server started by the coding assistant can remain running without a terminal window you opened. These are ordinary local Python processes and do not require the assistant to stay available.

Inspect occupied ports:

~~~bash
lsof -nP -iTCP:8001 -sTCP:LISTEN
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8082 -sTCP:LISTEN
~~~

If the existing frontend serves this project's dist/, reuse it. For a fresh restart, press Ctrl+C in its terminal. For a background process, replace PID below with the number from lsof, inspect it, and stop it only after confirming it is your project server:

~~~bash
ps -p PID -o command=
kill PID
~~~

Then start the documented command in your own terminal. After restarting your Mac, start both servers again. Stop each server with Ctrl+C and run deactivate to leave the virtual environment.

### 8. Run automated backend tests

In a separate terminal:

~~~bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity
source backend/.venv-langchain/bin/activate
cd backend
python -m unittest discover -s tests -v
~~~

These tests mock Groq responses and do not spend API quota. They cover request validation, health, CORS, urgent-response bypass, the LangChain/OpenAI request format, and provider errors.

## Vercel deployment

Deploy or verify the backend first. Your existing production origin is **https://maternity-taupe.vercel.app**. Use that project's dashboard to update it rather than creating another project.

### 1. Prepare the repository

Push the project to its Git repository, including backend/api/, backend/requirements.txt, backend/.python-version, and backend/vercel.json. Do not upload .env, virtual environments, or API keys. Use the CLI alternative below if you do not want Git-based deployment.

For this project, the GitHub repository is https://github.com/srijay/maternity and the production branch is main. Confirm the hosting projects track that repository and branch. Settings in the hosting dashboards cannot be verified from local files alone.

If Netlify is already connected to the same repository, pause its automatic publishing during initial migration until the backend and frontend configuration are ready.

### 2. Set Vercel project settings

For a repository containing the whole project:

| Setting | Value |
| --- | --- |
| Root Directory | backend |
| Framework Preset | Other |
| Build Command | No custom override |
| Output Directory | No custom override |
| Python | 3.12, from backend/.python-version |

Remove any old FastAPI framework/build overrides. This project uses file-based Python handlers under api/, not a FastAPI application. If importing for the first time, use Add New > Project and apply these same settings.

Vercel maps api/ask.py to /api/ask and api/health.py to /api/health. The included vercel.json rewrites /health to /api/health and sets a 60-second function limit.

### 3. Add production environment variables

In the Vercel project's Settings > Environment Variables, enter:

| Name | Production value |
| --- | --- |
| GROQ_API_KEY | Your actual Groq key |
| GROQ_MODEL | openai/gpt-oss-120b |
| ALLOWED_ORIGINS | https://fantastic-youtiao-51e03c.netlify.app |

Select Production. Add Preview values separately if testing preview deployments. Use the actual current Netlify origin if renamed; multiple origins are comma-separated, without paths or trailing slashes.

Your local .env is not deployed. Save these variables in Vercel and redeploy for changes to take effect.

### 4. Deploy and check access

Deploy the latest commit, or redeploy the existing project after settings changes. Wait for the deployment status to be Ready. Ensure the production domain remains **maternity-taupe.vercel.app**.

The API must be accessible without a Vercel login to serve public website visitors. If production Deployment Protection blocks it, adjust that project's protection settings. Never put bypass secrets in frontend code.

### 5. Verify the backend endpoints

Open these URLs:

- https://maternity-taupe.vercel.app/health
- https://maternity-taupe.vercel.app/api/health

Both should return JSON with status "ok". Then test a real answer:

~~~bash
curl -i https://maternity-taupe.vercel.app/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Reply with: ready"}'
~~~

Expect HTTP 200 with answer and model. Do not assume a Ready deployment or a configured health check proves Groq calls work.

Opening **https://maternity-taupe.vercel.app/** may show "This page doesn't exist": there is no root homepage in the backend. There is also no /docs page. The website itself lives on Netlify.

If /health fails but /api/health works, check that backend/vercel.json is included and the Root Directory is correct. If both return 404, check the deployed commit, Root Directory, framework preset, and whether api/ask.py and api/health.py appear as deployed functions. If a function returns 500, inspect Vercel runtime logs for import or dependency errors. An HTML login response indicates access protection, not a Groq error.

### Vercel CLI alternative

For the existing Git-linked project whose Root Directory is backend, run the CLI from the repository root so that setting is applied exactly once:

~~~bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity
npm install -g vercel
vercel login
vercel link
vercel --prod
~~~

When linking, select the existing project associated with maternity-taupe.vercel.app. Check environment variables and run the endpoint tests above afterward.

For a separate backend-only CLI project with no repository-root configuration, run from backend/ and use "." as its code directory; do not also set a nested backend Root Directory. Avoid creating a second project when updating your existing production URL.

## Netlify deployment

### 1. Confirm the production backend address

The complete config.js should contain this local/production selection:

~~~javascript
window.MATRACARE_CONFIG = {
  apiBaseUrl: ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? ""
    : "https://maternity-taupe.vercel.app"
};
~~~

The checked-in config selects the local backend automatically on localhost. It uses the Vercel origin everywhere else. Do not append /api/ask and do not put a Groq key in this file.

### 2. Build the public frontend

From the repository root:

~~~bash
cd /Users/srijaydeshpande/Desktop/Srijay/codes/maternity
node scripts/build-frontend.mjs
~~~

The generated dist/ contains index.html, styles.css, app.js, config.js, and assets/. It does not contain the Python backend or .env.

### 3. Update the existing Netlify site

Use the existing Netlify project for **https://fantastic-youtiao-51e03c.netlify.app**. Do not create or rename a site. Updating its deployment preserves its address.

Choose one deployment method.

**Manual upload**

1. Open the existing site's Deploys page.
2. Upload the generated dist/ folder using that site's deployment dropzone.
3. Wait for the production deployment to finish.
4. Refresh the existing website URL.

Build locally before manual upload. Upload dist/, not the entire source repository.

If the existing site uses Git-based deployment and does not show a manual dropzone, follow the Git deployment method below. Do not use a new-site dropzone, which would create another URL.

**Git deployment**

1. Connect the repository to the existing Netlify project, or keep its current repository connection.
2. Use the settings below, which match netlify.toml.
3. Remove an old Functions directory override pointing to netlify/functions.
4. Push the configuration and source changes, then trigger or allow the production build.

| Setting | Value |
| --- | --- |
| Base directory | Repository root |
| Build command | node scripts/build-frontend.mjs |
| Publish directory | dist |
| Backend functions | None on Netlify |

The Groq key belongs only on Vercel. Remove obsolete Netlify Groq variables after the new deployment works.

### 4. Verify the complete deployment

1. Confirm the Vercel health and real-answer tests pass.
2. Open https://fantastic-youtiao-51e03c.netlify.app and click Test LLM.
3. Submit a non-urgent question.
4. In browser Developer Tools > Network, inspect the ask request. It should go to https://maternity-taupe.vercel.app/api/ask, not localhost.
5. Stop your local servers and reload the deployed website. It should still work.

If curl works but the browser fails, check ALLOWED_ORIGINS, Deployment Protection, and the browser's OPTIONS preflight request. Include every frontend origin you actually use: the Netlify domain, a custom domain, or an approved preview origin. Redeploy Vercel after changing the list.

Local ports 8001, 8080, and 8082 are not production ports. Visitors use the HTTPS domains, and your Mac does not need to remain running.

## Updating and troubleshooting

### Publish later changes through Git

From the project root, inspect status and changes before committing:

~~~bash
git status
git diff
~~~

Stage only the files you intentionally changed and commit them. For example, for a README-only edit:

~~~bash
git add README.md
git commit -m "Update development and deployment instructions"
~~~

With a clean working tree, synchronize and push:

~~~bash
git pull --no-rebase origin main
git push origin main
~~~

The explicit merge option preserves local and remote commits if the branches diverge. If Git reports conflicts, stop before pushing, resolve the marked files, stage them, and complete the merge commit. Do not force-push to solve ordinary divergence. Keep both localhost detection and the production Vercel URL when resolving config.js.

Pushing main can trigger both connected hosting projects. Wait for their deployment results and repeat the endpoint and browser checks. If using manual Netlify deployment, Git push does not update that site: rebuild and upload dist/ separately. Environment-variable changes are made in the relevant host dashboard and require redeployment, not a Git commit containing the key.

### Common issues

| Symptom or change | Action |
| --- | --- |
| Key rejected | Correct GROQ_API_KEY in local .env or Vercel settings, then restart/redeploy |
| Model unavailable | Choose an enabled Groq model, update GROQ_MODEL, then restart/redeploy |
| Health says configured but answers fail | Health only checks key presence; use the real POST test |
| Groq rate limit / 429 | Wait or review provider quota |
| API timeout | Groq timeout is 25 seconds; browser deadline is 35 seconds |
| Frontend edits not visible | Rebuild dist/ and refresh locally; rebuild/redeploy Netlify in production |
| Backend edits not visible | Restart dev.py locally or redeploy Vercel |
| .env edits not taking effect | Restart Python; clear previously exported variables that override the file |
| Moved folder breaks activation or pip | Check command -v python; repair/recreate the venv at the new location |
| Root Vercel URL returns 404 | Test /health and /api/health; the backend has no homepage |
| Netlify homepage returns 404 | Confirm dist/index.html is in the published deployment |
| Wrong frontend port causes CORS error | Add its full origin to ALLOWED_ORIGINS and restart Python |

Do not rely on error messages alone to verify where requests go: the browser Network panel shows the destination, request payload, HTTP status, and JSON response. Avoid sharing API keys or sensitive user questions when reporting errors.

## Project limitations and hosting

This is an educational prototype. Existing urgent-keyword checks are not clinically validated triage. The app does not yet retrieve PubMed articles, store conversation history, or implement authentication and shared rate limiting. LangChain orchestrates the model call; it does not automatically add research retrieval.

Vercel Hobby is intended for personal, non-commercial use within its limits. Groq usage and quotas are separate from website hosting. Check provider terms before launching a commercial service.

## References

- [Vercel file-based Python functions](https://vercel.com/docs/functions/runtimes/python/api-directory)
- [Vercel Python runtime and versions](https://vercel.com/docs/functions/runtimes/python)
- [Vercel CLI deployment](https://vercel.com/docs/cli/deploy)
- [Vercel repository root and CLI setup](https://vercel.com/docs/monorepos)
- [Netlify deployment methods](https://docs.netlify.com/deploy/create-deploys/)
- [LangChain ChatOpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [Vercel fair-use rules](https://vercel.com/docs/limits/fair-use-guidelines)
