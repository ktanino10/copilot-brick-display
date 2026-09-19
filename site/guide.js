const modelInput = document.querySelector('#guide-model');
const stepInput = document.querySelector('#guide-step');
const image = document.querySelector('#guide-drawing');
const response = await fetch('assets/catalog.json');
if (!response.ok) throw new Error(`工程データを取得できません: ${response.status}`);
const catalog = await response.json();
const requested = new URLSearchParams(location.search).get('model');
modelInput.value = ['A', 'B', 'C'].includes(requested) ? requested : 'B';

function showStep() {
  image.src = `drawings/${modelInput.value}/step-${String(stepInput.value).padStart(2, '0')}.svg`;
  image.alt = `${modelInput.value} / ${stepInput.selectedOptions[0].textContent}`;
}

function showModel() {
  const model = catalog.models.find((item) => item.id === modelInput.value);
  stepInput.replaceChildren();
  for (const step of model.steps) {
    stepInput.add(new Option(`${step.number} / ${model.steps.length} — ${step.title}`, step.number));
  }
  document.querySelector('#guide-pdf').href = `downloads/${model.id}/drawings.pdf`;
  showStep();
}
modelInput.addEventListener('change', showModel);
stepInput.addEventListener('change', showStep);
showModel();
