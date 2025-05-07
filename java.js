// Função para buscar o nome associado à matrícula
function buscarNome() {
  const matricula = document.getElementById('matricula').value;
  if (!matricula) return;

  fetch('/buscar_nome', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ matricula })
  })
  .then(res => res.json())
  .then(data => {
    if (data.nome) {
      document.getElementById('nome_exibido').innerText = 'Nome: ' + data.nome;
      document.getElementById('nome').value = data.nome;
      document.getElementById('loginForm').querySelector('button').disabled = false;
    } else {
      document.getElementById('nome_exibido').innerText = 'Cadastro não encontrado. Faça o cadastro.';
      document.getElementById('nome').value = '';
      document.getElementById('loginForm').querySelector('button').disabled = true;
    }
  })
  .catch(err => {
    console.error('Erro ao buscar nome:', err);
    document.getElementById('nome_exibido').innerText = 'Matrícula não encontrada! Faça o Cadastro';
  });
}
function aplicarFiltros() {
  const rotaFiltro = document.getElementById('filtroRota').value.toLowerCase();
  const cidadeFiltro = document.getElementById('filtroCidade').value.toLowerCase();
  const entregaFiltro = document.getElementById('filtroEntrega').value.toLowerCase();
  const separacaoFiltro = document.getElementById('filtroSeparacao').value;

  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {
    const rota = card.dataset.rota || '';
    const cidade = card.dataset.cidade || '';
    const entrega = card.dataset.entrega || '';
    const estaSeparado = card.classList.contains('separado');

    const rotaOk = rota.includes(rotaFiltro);
    const cidadeOk = cidade.includes(cidadeFiltro);
    const entregaOk = entregaFiltro === '' || entrega === entregaFiltro;
    const separacaoOk = separacaoFiltro === '' ||
      (separacaoFiltro === 'separado' && estaSeparado) ||
      (separacaoFiltro === 'nao-separado' && !estaSeparado);

    if (rotaOk && cidadeOk && entregaOk && separacaoOk) {
      card.style.display = '';
    } else {
      card.style.display = 'none';
    }
  });
}
function limparFiltro() {
  // Limpa os campos de filtro
  document.getElementById('data').value = '';
  document.getElementById('filtroRota').value = '';
  document.getElementById('filtroCidade').value = '';
  document.getElementById('filtroEntrega').value = '';
  document.getElementById('filtroSeparacao').value = '';

  // Recarrega a página de registros sem filtros (sem parâmetros na URL)
  window.location.href = '/registros';
  
  // Aplica os filtros (que estarão todos vazios agora)
  aplicarFiltros();
}
function onDblClick(card, id) {
  // Verifica se o card já está marcado como separado
  if (card.classList.contains('separado')) {
    return; // Não faz nada se já estiver separado
  }

  // Adiciona o estilo "separado" e o texto "Em Separação"
  card.classList.add('separado');
  const label = document.createElement('span');
  label.textContent = "Em Separação";
  label.classList.add('em-separacao-label');
  card.appendChild(label);

  // Envia a requisição para o servidor para atualizar o estado
  fetch(`/atualizar_separacao/${id}`, {
    method: 'POST',
    body: JSON.stringify({ em_separacao: 1 }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log("Estado de separação atualizado.");
    }
  });
}
function onDblClick(card, id) {
  if (!card.classList.contains('separado')) {
    card.classList.add('separado');

    if (!card.querySelector('.em-separacao-label')) {
      const label = document.createElement('span');
      label.textContent = "Em Separação";
      label.classList.add('em-separacao-label');
      card.appendChild(label);
    }

    fetch(`/atualizar_separacao/${id}`, {
      method: 'POST',
      body: JSON.stringify({ em_separacao: 1 }),
      headers: {
        'Content-Type': 'application/json'
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        console.log("Estado de separação atualizado.");
      }
    });
  }
}
