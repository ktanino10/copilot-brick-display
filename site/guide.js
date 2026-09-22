const modelInput = document.querySelector('#guide-model');
const stepInput = document.querySelector('#guide-step');
const image = document.querySelector('#guide-drawing');
const revision = new URL(import.meta.url).searchParams.get('rev');
modelInput.disabled = true;
stepInput.disabled = true;
async function initialize() {
  if (!revision) throw new Error('工程表示のリビジョンが指定されていません。サイトから開き直してください。');
  const response = await fetch(`assets/catalog.json?rev=${encodeURIComponent(revision)}`);
  if (!response.ok) throw new Error(`工程データを取得できません: ${response.status}`);
  const catalog = await response.json();
  if (catalog.revision !== revision) throw new Error('設計リビジョンが一致しません。再読込してください。');
  const requested = new URLSearchParams(location.search).get('model');
  modelInput.value = ['A', 'B', 'C'].includes(requested) ? requested : 'B';

  function showStep() {
    image.src = `drawings/${modelInput.value}/step-${String(stepInput.value).padStart(2, '0')}.svg?rev=${revision}`;
    image.alt = `${modelInput.value} / ${stepInput.selectedOptions[0].textContent}`;
  }

  function showModel() {
    const model = catalog.models.find((item) => item.id === modelInput.value);
    stepInput.replaceChildren();
    for (const step of model.steps) {
      stepInput.add(new Option(`${step.number} / ${model.steps.length} — ${step.title}`, step.number));
    }
    document.querySelector('#guide-pdf').href = `downloads/${model.id}/drawings.pdf?rev=${revision}`;
    showStep();
  }
  modelInput.addEventListener('change', showModel);
  stepInput.addEventListener('change', showStep);
  showModel();
  modelInput.disabled = false;
  stepInput.disabled = false;
}

initialize().catch((error) => {
  const alert = document.querySelector('#guide-data-error');
  alert.hidden = false;
  alert.textContent = `工程表示を開始できません: ${error.message}`;
  image.hidden = true;
  document.querySelector('#guide-pdf').hidden = true;
  console.error(error);
});
