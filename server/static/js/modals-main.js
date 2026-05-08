function openMetricsModal(platform = 'all') {
  if (typeof MetricsModal !== 'undefined' && MetricsModal.open) MetricsModal.open(platform);
  else console.error('MetricsModal not loaded');
}

function openAIAnalysisModal() {
  if (typeof AIAnalysisModal !== 'undefined' && AIAnalysisModal.open) AIAnalysisModal.open();
  else console.error('AIAnalysisModal not loaded');
}

function openABTestModal() {
  if (typeof ABTestModal !== 'undefined' && ABTestModal.open) ABTestModal.open();
  else console.error('ABTestModal not loaded');
}

function closeAllModals() {
  if (typeof MetricsModal !== 'undefined' && MetricsModal.close) MetricsModal.close();
  if (typeof AIAnalysisModal !== 'undefined' && AIAnalysisModal.close) AIAnalysisModal.close();
  if (typeof ABTestModal !== 'undefined' && ABTestModal.close) ABTestModal.close();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAllModals(); });

window.openMetricsModal = openMetricsModal;
window.openAIAnalysisModal = openAIAnalysisModal;
window.openABTestModal = openABTestModal;
window.closeAllModals = closeAllModals;

console.log('✅ Модальні вікна завантажено: openMetricsModal(), openAIAnalysisModal(), openABTestModal()');