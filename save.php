<?php

// Pega a requisição post e transforma em JSON.
$values = json_encode($_POST);

// Armazena no final do arquivo os valores recebidos.
file_put_contents('nome_e_path_do_arquivo.ext', $values, FILE_APPEND);

// Verifica se algo foi postado
if ( ! empty( $_POST ) ) {
	// <input type="text" name="nome">
	echo 'Nome: ' . $_POST['nome'] . '<br>';

	// <input type="email" name="email">
	echo 'Email: ' . $_POST['email'] . '<br>';
	
	// <input type="text" name="telefone">
	echo 'Telefone: ' . $_POST['telefone'] . '<br>';
	
	// <input type="text" name="endereco">
	echo 'Endereço: ' . $_POST['endereco'] . '<br>';
}
?>