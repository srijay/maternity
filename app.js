const $ = (id) => document.getElementById(id);
const apiBase = (window.MATRACARE_CONFIG?.apiBaseUrl ||
  (["localhost", "127.0.0.1"].includes(location.hostname) ? "http://localhost:8001" : "")).replace(/\/$/, "");
const initialAnswer = $("answer").innerHTML;
let mode = "mother";
let activeRequest = null;
let testBusy = false;
// Fast, offline warning only; the backend repeats this check before any model call.
const urgentKeywords = /bleeding|passing clots|severe.{0,30}pain|sharp.{0,30}pain|faint|collapse|seizure|convulsion|chest pain|shortness of breath|cannot breathe|trouble breathing|severe headache|blurred vision|blurry vision|vision changes|swelling.{0,20}face|reduced.{0,20}movement|less.{0,20}movement|baby.{0,20}not moving|no movement|water broke|fluid leaking|preterm labo[u]?r|regular contractions|high fever|fever.{0,20}pain|harm myself|suicid/i;

const examples = {
  mother: [
    ["Staying active", "What does research say about staying active during pregnancy?"],
    ["Nutrition", "What does research say about a balanced diet during pregnancy?"],
    ["Sleep", "What does research say about sleep quality during pregnancy?"]
  ],
  clinician: [
    ["Gestational diabetes", "What do systematic reviews report about exercise and gestational diabetes prevention?"],
    ["Postpartum care", "What is the evidence for pelvic floor training after childbirth?"]
  ]
};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function link(text, url) {
  const node = element("a", text);
  node.href = url;
  node.target = "_blank";
  node.rel = "noopener noreferrer";
  return node;
}
function resetAnswer() {
  $("answer").innerHTML = initialAnswer;
  if (mode === "clinician") {
    $("answer").querySelector("h3").textContent = "A closer look at your clinical question.";
    $("answer").querySelector("p").textContent = "Clinical interpretation and supporting literature.";
  }
  $("evidence-section").hidden = true;
  $("evidence-list").replaceChildren();
  $("search-record").replaceChildren();
  $("request-status").textContent = "";
  $("result-label").textContent = "Not started";
}
function setBusy(busy) {
  $("submit-question").disabled = busy;
  $("test-llm").disabled = busy || testBusy;
  $("cancel-request").hidden = !busy;
  $("answer").setAttribute("aria-busy", String(busy));
  $("submit-question").textContent = busy ? "Working..." : mode === "mother" ? "Get guidance" : "Review evidence";
}
function cancel() {
  activeRequest?.abort();
  activeRequest = null;
  setBusy(false);
}
function setMode(value) {
  cancel();
  mode = value;
  document.body.dataset.mode = mode;
  $("mother-context").hidden = mode !== "mother";
  $("clinician-context").hidden = mode !== "clinician";
  $("response-heading").textContent = mode === "mother" ? "Your guidance" : "Clinical response";
  $("question-label").textContent = mode === "mother" ? "What is on your mind?" : "Your clinical question";
  $("question").placeholder = examples[mode][0][1];
  $("context-title").replaceChildren(document.createTextNode(mode === "mother" ? "Your context " : "Search parameters "), element("span", "Optional", "muted"));
  $("examples").replaceChildren(...examples[mode].map(([label, question]) => {
    const button = element("button", label, "example");
    button.type = "button";
    button.addEventListener("click", () => { $("question").value = question; $("question").focus(); });
    return button;
  }));
  resetAnswer();
  setBusy(false);
}
async function request(payload, controller) {
  const timer = setTimeout(() => controller.abort("timeout"), 57000);
  try {
    const response = await fetch(`${apiBase}/api/ask`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload), signal: controller.signal
    });
    let data;
    try { data = await response.json(); } catch { throw new Error("The backend returned an unreadable response. Check its deployment."); }
    if (!response.ok) throw new Error(data.error || "The service is unavailable. Please try again.");
    if (typeof data.answer !== "string") throw new Error("The backend returned an incomplete response.");
    return data;
  } catch (error) {
    if (controller.signal.reason === "timeout") throw new Error("The request timed out. Please try a more focused question.");
    if (error instanceof TypeError) throw new Error("Cannot reach the backend. Check the service address, connection and allowed origins.");
    throw error;
  } finally { clearTimeout(timer); }
}
function showEvidence(data) {
  if (mode !== "clinician") {
    $("evidence-section").hidden = true;
    $("evidence-list").replaceChildren();
    $("search-record").replaceChildren();
    return;
  }
  const sources = data.sources || [];
  const searches = data.searches || [];
  $("evidence-section").hidden = !sources.length && !searches.length;
  $("source-count").textContent = `${sources.length} paper${sources.length === 1 ? "" : "s"}`;
  const list = $("evidence-list");
  list.replaceChildren();
  if (mode === "clinician" && sources.length) {
    const wrap = element("div", undefined, "evidence-table-wrap");
    const table = element("table");
    const head = element("thead");
    const row = element("tr");
    ["PMID", "Year", "Publication type"].forEach((text) => { const th = element("th", text); th.scope = "col"; row.append(th); });
    head.append(row);
    const body = element("tbody");
    sources.forEach((source) => {
      const row = element("tr");
      [source.pmid, source.year || "Not reported", source.publication_types.join(", ") || "Not indexed"].forEach((value) => row.append(element("td", value)));
      body.append(row);
    });
    table.append(head, body); wrap.append(table); list.append(wrap);
  }
  sources.forEach((source, index) => {
    const details = element("details", undefined, "evidence-item");
    details.id = `paper-${source.pmid}`;
    details.append(element("summary", `${index + 1}. ${source.title}`));
    details.append(element("p", [source.journal, source.year, ...source.publication_types].filter(Boolean).join(" · "), "paper-meta"));
    details.append(element("p", source.abstract || "No abstract available.", "abstract"));
    if (source.abstract_truncated) details.append(element("p", "Abstract excerpt; truncated for length.", "muted small"));
    const paperLink = link(`PubMed · PMID ${source.pmid}`, `https://pubmed.ncbi.nlm.nih.gov/${encodeURIComponent(source.pmid)}/`);
    paperLink.className = "paper-link";
    details.append(paperLink); list.append(details);
  });
  $("search-record").replaceChildren();
  searches.forEach((search) => {
    const block = element("div");
    block.append(element("p", `${search.total} matches; ${search.pmids.length} IDs returned. Ranked by relevance.`));
    block.append(element("code", search.query));
    if (search.translated_query !== search.query) block.append(element("p", `NCBI translation: ${search.translated_query}`));
    if (Object.keys(search.warnings || {}).length) block.append(element("p", `NCBI notice: ${JSON.stringify(search.warnings)}`));
    $("search-record").append(block);
  });
  if (data.excluded_count) $("search-record").append(element("p", `${data.excluded_count} record(s) excluded: missing abstracts or retraction/concern notices.`));
}
function citations(pmids) {
  const refs = element("div", undefined, "citations");
  refs.setAttribute("aria-label", "Supporting papers");
  pmids.forEach((pmid) => {
    const a = element("a", `PMID ${pmid}`);
    a.href = `#paper-${pmid}`;
    a.addEventListener("click", () => { const paper = $(`paper-${pmid}`); if (paper) paper.open = true; });
    refs.append(a);
  });
  return refs;
}
function answerParagraph(text, className) {
  const paragraph = element("p", undefined, className);
  let offset = 0;
  // Support bold only; all model text stays in text nodes, never parsed HTML.
  for (const match of text.matchAll(/\*\*([^*\n]+)\*\*/g)) {
    paragraph.append(text.slice(offset, match.index), element("strong", match[1]));
    offset = match.index + match[0].length;
  }
  paragraph.append(text.slice(offset));
  return paragraph;
}
function answerSection(title, text, className = "answer-section") {
  const section = element("section", undefined, className);
  section.append(element("h3", title), answerParagraph(text));
  return section;
}
function showAnswer(data) {
  const answer = $("answer");
  answer.replaceChildren();
  if (data.status === "complete") {
    if (mode === "mother") {
      answer.append(answerParagraph(data.answer, "guidance-intro"));
      answer.append(answerSection("What you can do next", data.next_steps, "answer-section next-steps"));
      answer.append(answerSection("Keep in mind", data.limitations));
    } else {
      const overview = answerSection("Overall answer", data.overview || data.answer, "clinical-overview");
      overview.append(element("p", "Clinical interpretation includes general model knowledge, which is not verified current guidance. Linked papers inform the interpretation, not every statement.", "interpretation-note"));
      if (data.overview_pmids?.length) overview.append(citations(data.overview_pmids));
      answer.append(overview);
      const findings = element("section", undefined, "findings-section");
      findings.append(element("h3", "What the papers report"));
      const list = element("ol", undefined, "findings-list");
      data.findings.forEach((finding) => {
        const block = element("li", undefined, "finding");
        block.append(answerParagraph(finding.text), citations(finding.pmids));
        list.append(block);
      });
      findings.append(list); answer.append(findings);
      answer.append(answerSection("Limitations & uncertainty", data.limitations));
      answer.append(answerSection("Implications & further appraisal", data.next_steps, "answer-section next-steps"));
    }
  } else {
    const block = element("div", undefined, data.status === "urgent" ? "urgent" : "");
    if (data.status === "urgent") block.append(element("h3", "Please seek care now"));
    block.append(answerParagraph(data.answer)); answer.append(block);
  }
  $("result-label").textContent = ({ complete: mode === "mother" ? "Guidance" : "Research informed", urgent: "Urgent", no_evidence: mode === "mother" ? "Unable to answer" : "No usable evidence", unverified: "Answer withheld" })[data.status] || "Response";
  if (data.disclaimer && mode === "clinician") answer.append(element("p", data.disclaimer, "answer-disclaimer"));
  showEvidence(data);
  if (matchMedia("(max-width: 680px)").matches) $("response-heading").scrollIntoView({ block: "start" });
}

$("question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!$("question").value.trim()) return;
  cancel();
  if (mode === "mother" && urgentKeywords.test($("question").value)) {
    resetAnswer();
    showAnswer({ status: "urgent", answer: "Contact your maternity unit, clinician or local emergency service now. Do not wait for an online answer if symptoms are severe, sudden, worsening or feel unsafe. For heavy bleeding, severe pain, fainting, chest pain, seizure or trouble breathing, seek emergency help immediately. For reduced or changed baby movements, contact your maternity unit now. Tell the care team whether you are pregnant or recently gave birth.", sources: [], searches: [] });
    return;
  }
  const controller = new AbortController();
  activeRequest = controller;
  resetAnswer();
  $("answer").replaceChildren();
  $("request-status").textContent = mode === "mother" ? "Preparing your guidance..." : "Reviewing the literature and preparing a clinical response...";
  $("result-label").textContent = "In progress";
  setBusy(true);
  const payload = { mode, question: $("question").value.trim() };
  if (mode === "mother") Object.assign(payload, { stage: $("stage").value, week: $("stage").value === "pregnancy" ? $("week").value || "unknown" : "unknown", country: $("country").value, risk: $("risk").value });
  else payload.pubmed_query = $("pubmed-query").value.trim();
  try {
    const data = await request(payload, controller);
    if (activeRequest !== controller) return;
    showAnswer(data);
    $("request-status").textContent = "";
  } catch (error) {
    if (activeRequest !== controller) return;
    $("answer").replaceChildren(element("p", error.message, "error-message"));
    $("request-status").textContent = "No answer was generated.";
    $("result-label").textContent = "Unavailable";
  } finally {
    if (activeRequest === controller) { activeRequest = null; setBusy(false); }
  }
});
$("test-llm").addEventListener("click", async () => {
  testBusy = true;
  $("test-llm").disabled = true;
  $("connection").classList.remove("error");
  $("connection").textContent = "Testing Groq...";
  try {
    const data = await request({ action: "test" }, new AbortController());
    $("connection").textContent = `Connected · ${data.model}`;
  } catch (error) {
    $("connection").textContent = error.message;
    $("connection").classList.add("error");
  } finally {
    testBusy = false;
    $("test-llm").disabled = Boolean(activeRequest);
  }
});
$("cancel-request").addEventListener("click", () => { cancel(); resetAnswer(); $("request-status").textContent = "Request cancelled. Server processing may still finish."; });
$("clear-question").addEventListener("click", () => { cancel(); $("question-form").reset(); $("week").disabled = false; resetAnswer(); $("question").focus(); });
document.querySelectorAll('input[name="mode"]').forEach((input) => input.addEventListener("change", () => setMode(input.value)));
$("stage").addEventListener("change", () => { $("week").disabled = $("stage").value !== "pregnancy"; });
setMode("mother");
