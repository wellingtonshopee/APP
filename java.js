function verificarCampos(id) {
  const gaiola = document.getElementById('gaiola_' + id);
  const posicao = document.getElementById('posicao_' + id);
  const salvarBtn = document.getElementById('salvar_' + id);
  const card = document.getElementById('card_' + id);

  const gaiolaPreenchida = gaiola.value.trim() !== '';
  const posicaoPreenchida = posicao.value.trim() !== '';

  // Estiliza conforme preenchimento
  gaiola.style.backgroundColor = gaiolaPreenchida ? '#e4ebe4' : '';
  posicao.style.backgroundColor = posicaoPreenchida ? '#e4ebe4' : '';

  if (gaiolaPreenchida && posicaoPreenchida) {
    salvarBtn.disabled = false;
    salvarBtn.style.visibility = 'visible';
    card.style.backgroundColor = '#e4ebe4b6';
  } else {
    salvarBtn.disabled = true;
    card.style.backgroundColor = '';
  }

  // Controle de foco automático
  if (gaiolaPreenchida && !posicaoPreenchida) {
    posicao.focus();
  } else if (gaiolaPreenchida && posicaoPreenchida) {
    salvarBtn.focus();
  }
}
