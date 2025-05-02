function verificarCampos(id) {
  const gaiola = document.getElementById('gaiola_' + id);
  const posicao = document.getElementById('posicao_' + id);
  const salvarBtn = document.getElementById('salvar_' + id);
  const card = document.getElementById('card_' + id);

  // Verificar se os campos estão vazios
  if (gaiola.value.trim() === '' || posicao.value.trim() === '') {
    salvarBtn.disabled = true;
    // Alterar a cor do fundo dos campos para o normal (branco)
    gaiola.style.backgroundColor = '';
    posicao.style.backgroundColor = '';
    // Alterar a cor de fundo do card para o normal
    card.style.backgroundColor = '';
  } else {
    salvarBtn.disabled = false;
    // Alterar a cor do fundo dos campos para indicar que estão preenchidos
    gaiola.style.backgroundColor = '#e4ebe4';
    posicao.style.backgroundColor = '#e4ebe4';
    // Alterar a cor de fundo do card
    card.style.backgroundColor = '#e4ebe4b6'; // Cor modificada para o preenchido
  }
}
