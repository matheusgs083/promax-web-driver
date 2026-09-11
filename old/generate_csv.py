import pandas as pd
from pathlib import Path

# Section 1: Notas / Títulos
notas_data = [
    {"UNB_Codigo": "19193", "Razao_Social": "FILIPE SILVA RODRIGUES", "Nota": "204.500", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 215.97, "Devolucao": 0.0, "Valor_Liquido": 215.97},
    {"UNB_Codigo": "15216", "Razao_Social": "PAULO MARCIO BATISTA PEREIR", "Nota": "204.501", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 4 DIAS", "Valor_Nota": 301.73, "Devolucao": 0.0, "Valor_Liquido": 301.73},
    {"UNB_Codigo": "17295", "Razao_Social": "LUCAS MARTINS", "Nota": "204.502", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 66.18, "Devolucao": 0.0, "Valor_Liquido": 66.18},
    {"UNB_Codigo": "17295", "Razao_Social": "LUCAS MARTINS", "Nota": "204.502", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 396.57, "Devolucao": 0.0, "Valor_Liquido": 396.57},
    {"UNB_Codigo": "19300", "Razao_Social": "LUCAS ALVES MARTINS BIG BUR", "Nota": "204.503", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 188.96, "Devolucao": 0.0, "Valor_Liquido": 188.96},
    {"UNB_Codigo": "19300", "Razao_Social": "LUCAS ALVES MARTINS BIG BUR", "Nota": "204.504", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 1216.36, "Devolucao": 0.0, "Valor_Liquido": 1216.36},
    {"UNB_Codigo": "16824", "Razao_Social": "GABRIEL DOS SANTOS VENANCIO", "Nota": "204.505", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 229.63, "Devolucao": 0.0, "Valor_Liquido": 229.63},
    {"UNB_Codigo": "18318", "Razao_Social": "60.902.081 JOAO BATISTA DOS", "Nota": "204.506", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 169.90, "Devolucao": 0.0, "Valor_Liquido": 169.90},
    {"UNB_Codigo": "18725", "Razao_Social": "GUSTAVO JUSTINO DE MORAES", "Nota": "204.507", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 590.26, "Devolucao": 0.0, "Valor_Liquido": 590.26},
    {"UNB_Codigo": "12145", "Razao_Social": "ANA CLAUDIA SANTOS OLIVEIRA", "Nota": "204.508", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 2435.12, "Devolucao": 0.0, "Valor_Liquido": 2435.12},
    {"UNB_Codigo": "12145", "Razao_Social": "ANA CLAUDIA SANTOS OLIVEIRA", "Nota": "204.508", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 167.52, "Devolucao": 0.0, "Valor_Liquido": 167.52},
    {"UNB_Codigo": "18267", "Razao_Social": "MATHEUS VENANCIO DOS SANTOS", "Nota": "204.509", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 3 DIAS", "Valor_Nota": 331.01, "Devolucao": 0.0, "Valor_Liquido": 331.01},
    {"UNB_Codigo": "18620", "Razao_Social": "62.433.689 FELIPE RODRIGUES", "Nota": "204.510", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 2 DIAS", "Valor_Nota": 1089.99, "Devolucao": 0.0, "Valor_Liquido": 1089.99},
    {"UNB_Codigo": "18620", "Razao_Social": "62.433.689 FELIPE RODRIGUES", "Nota": "204.510", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 151.50, "Devolucao": 0.0, "Valor_Liquido": 151.50},
    {"UNB_Codigo": "17887", "Razao_Social": "MARCOS ANTONIO CANTALICE DE", "Nota": "204.511", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 529.98, "Devolucao": 0.0, "Valor_Liquido": 529.98},
    {"UNB_Codigo": "14144", "Razao_Social": "ROCHANNA KELLY VIEIRA JORGE", "Nota": "204.512", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS", "Valor_Nota": 70.85, "Devolucao": 0.0, "Valor_Liquido": 70.85},
    {"UNB_Codigo": "14144", "Razao_Social": "ROCHANNA KELLY VIEIRA JORGE", "Nota": "204.513", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS", "Valor_Nota": 620.21, "Devolucao": 0.0, "Valor_Liquido": 620.21},
    {"UNB_Codigo": "11524", "Razao_Social": "POSTO DIESEL SAO JOSE LTDA", "Nota": "204.514", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 11 DIAS", "Valor_Nota": 2013.97, "Devolucao": 0.0, "Valor_Liquido": 2013.97},
    {"UNB_Codigo": "18167", "Razao_Social": "SAVIO VITOR FREITAS QUEIROZ", "Nota": "204.515", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 2582.20, "Devolucao": 0.0, "Valor_Liquido": 2582.20},
    {"UNB_Codigo": "18167", "Razao_Social": "SAVIO VITOR FREITAS QUEIROZ", "Nota": "204.516", "Sit": "003", "Op": "115", "Condicao_Pagto": "COMODATO", "Valor_Nota": 4500.00, "Devolucao": 0.0, "Valor_Liquido": 4500.00},
    {"UNB_Codigo": "11534", "Razao_Social": "MARIA JOSE MARIANO DO NASCI", "Nota": "204.517", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 128.38, "Devolucao": 0.0, "Valor_Liquido": 128.38},
    {"UNB_Codigo": "11559", "Razao_Social": "JOSE VALDEMIR ALBUQUERQUE D", "Nota": "204.518", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 2230.40, "Devolucao": 0.0, "Valor_Liquido": 2230.40},
    {"UNB_Codigo": "11559", "Razao_Social": "JOSE VALDEMIR ALBUQUERQUE D", "Nota": "204.518", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 187.06, "Devolucao": 0.0, "Valor_Liquido": 187.06},
    {"UNB_Codigo": "11559", "Razao_Social": "JOSE VALDEMIR ALBUQUERQUE D", "Nota": "204.519", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 3031.15, "Devolucao": 0.0, "Valor_Liquido": 3031.15},
    {"UNB_Codigo": "17666", "Razao_Social": "51.562.852 EDILANIA JORGE D", "Nota": "204.520", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 269.10, "Devolucao": 0.0, "Valor_Liquido": 269.10},
    {"UNB_Codigo": "99174", "Razao_Social": "ERIVETE ROCHA DO NASCIMENTO", "Nota": "204.521", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 19.20, "Devolucao": 0.0, "Valor_Liquido": 19.20},
    {"UNB_Codigo": "99174", "Razao_Social": "ERIVETE ROCHA DO NASCIMENTO", "Nota": "204.522", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS 1%", "Valor_Nota": 3609.15, "Devolucao": 0.0, "Valor_Liquido": 3609.15},
    {"UNB_Codigo": "17836", "Razao_Social": "58.821.864 NATALIA EDJANE S", "Nota": "204.523", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 953.40, "Devolucao": 0.0, "Valor_Liquido": 953.40},
    {"UNB_Codigo": "17836", "Razao_Social": "58.821.864 NATALIA EDJANE S", "Nota": "204.524", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 2 DIAS", "Valor_Nota": 75.80, "Devolucao": 0.0, "Valor_Liquido": 75.80},
    {"UNB_Codigo": "19190", "Razao_Social": "GIZELDA TRAJANO DA SILVA", "Nota": "204.525", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 112.60, "Devolucao": 0.0, "Valor_Liquido": 112.60},
    {"UNB_Codigo": "15926", "Razao_Social": "ADELTON GOMES DE ANDRADE", "Nota": "204.526", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 360.36, "Devolucao": 0.0, "Valor_Liquido": 360.36},
    {"UNB_Codigo": "15926", "Razao_Social": "ADELTON GOMES DE ANDRADE", "Nota": "204.526", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 67.50, "Devolucao": 0.0, "Valor_Liquido": 67.50},
    {"UNB_Codigo": "17599", "Razao_Social": "MOISES PEREIRA", "Nota": "204.527", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 143.40, "Devolucao": 0.0, "Valor_Liquido": 143.40},
    {"UNB_Codigo": "17599", "Razao_Social": "MOISES PEREIRA", "Nota": "204.528", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 58.50, "Devolucao": 0.0, "Valor_Liquido": 58.50},
    {"UNB_Codigo": "19156", "Razao_Social": "RAFAEL NOGUEIRA FALCAO", "Nota": "204.529", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 617.46, "Devolucao": 0.0, "Valor_Liquido": 617.46},
    {"UNB_Codigo": "19156", "Razao_Social": "RAFAEL NOGUEIRA FALCAO", "Nota": "204.530", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 166.75, "Devolucao": 0.0, "Valor_Liquido": 166.75},
    {"UNB_Codigo": "11539", "Razao_Social": "MARIA GENILMA RODRIGUES ALV", "Nota": "204.531", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS", "Valor_Nota": 262.83, "Devolucao": 0.0, "Valor_Liquido": 262.83},
    {"UNB_Codigo": "11580", "Razao_Social": "JOSE BONIFACIO DA COSTA", "Nota": "204.532", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 535.10, "Devolucao": 0.0, "Valor_Liquido": 535.10},
    {"UNB_Codigo": "11580", "Razao_Social": "JOSE BONIFACIO DA COSTA", "Nota": "204.532", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 106.26, "Devolucao": 0.0, "Valor_Liquido": 106.26},
    {"UNB_Codigo": "12047", "Razao_Social": "ESTER BRASÍLIANA DE SOUZA P", "Nota": "204.533", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 85.44, "Devolucao": 0.0, "Valor_Liquido": 85.44},
    {"UNB_Codigo": "63612", "Razao_Social": "JOSE LEDO DA COSTA E CIA LT", "Nota": "204.534", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 11 DIAS 2,5%", "Valor_Nota": 2374.17, "Devolucao": 0.0, "Valor_Liquido": 2374.17},
    {"UNB_Codigo": "63612", "Razao_Social": "JOSE LEDO DA COSTA E CIA LT", "Nota": "204.535", "Sit": "003", "Op": "5", "Condicao_Pagto": "TROCA", "Valor_Nota": 18.77, "Devolucao": 0.0, "Valor_Liquido": 18.77},
    {"UNB_Codigo": "63612", "Razao_Social": "JOSE LEDO DA COSTA E CIA LT", "Nota": "204.536", "Sit": "003", "Op": "5", "Condicao_Pagto": "TROCA", "Valor_Nota": 66.12, "Devolucao": 0.0, "Valor_Liquido": 66.12},
    {"UNB_Codigo": "63612", "Razao_Social": "JOSE LEDO DA COSTA E CIA LT", "Nota": "204.537", "Sit": "003", "Op": "39", "Condicao_Pagto": "SIMPLES REMESSA", "Valor_Nota": 108.30, "Devolucao": 0.0, "Valor_Liquido": 108.30},
    {"UNB_Codigo": "15574", "Razao_Social": "AMANDA SANTO TRAJANO", "Nota": "204.538", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 4970.22, "Devolucao": 0.0, "Valor_Liquido": 4970.22},
    {"UNB_Codigo": "18457", "Razao_Social": "ERINALDA AVELINO DO NASCIME", "Nota": "204.539", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 157.92, "Devolucao": 0.0, "Valor_Liquido": 157.92},
    {"UNB_Codigo": "11515", "Razao_Social": "ROSILDA DE SOUZA SANTOS", "Nota": "204.540", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 242.94, "Devolucao": 0.0, "Valor_Liquido": 242.94},
    {"UNB_Codigo": "11515", "Razao_Social": "ROSILDA DE SOUZA SANTOS", "Nota": "204.541", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 2 DIAS", "Valor_Nota": 1991.71, "Devolucao": 0.0, "Valor_Liquido": 1991.71},
    {"UNB_Codigo": "11533", "Razao_Social": "MARIA DA LUZ XAVIER DOS SAN", "Nota": "204.542", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 4 DIAS", "Valor_Nota": 156.12, "Devolucao": 0.0, "Valor_Liquido": 156.12},
    {"UNB_Codigo": "15657", "Razao_Social": "JOSE WELINTON", "Nota": "204.543", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 823.90, "Devolucao": 0.0, "Valor_Liquido": 823.90},
    {"UNB_Codigo": "13554", "Razao_Social": "IZAAQUIEL DE JESUS DINIZ", "Nota": "204.544", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 174.56, "Devolucao": 0.0, "Valor_Liquido": 174.56},
    {"UNB_Codigo": "17154", "Razao_Social": "MARIA APARECIDA GOMES", "Nota": "204.545", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 204.88, "Devolucao": 0.0, "Valor_Liquido": 204.88},
    {"UNB_Codigo": "17154", "Razao_Social": "MARIA APARECIDA GOMES", "Nota": "204.546", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 101.05, "Devolucao": 0.0, "Valor_Liquido": 101.05},
    {"UNB_Codigo": "15905", "Razao_Social": "IVANINDO JOAQUIM DA SILVA", "Nota": "204.547", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 148.29, "Devolucao": 0.0, "Valor_Liquido": 148.29},
    {"UNB_Codigo": "18125", "Razao_Social": "JOSÉ ALEQSSANDRO LOURENÇO L", "Nota": "204.548", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 3537.21, "Devolucao": 0.0, "Valor_Liquido": 3537.21},
    {"UNB_Codigo": "11512", "Razao_Social": "RUI DE FARIAS FALCAO ME", "Nota": "204.549", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 688.42, "Devolucao": 0.0, "Valor_Liquido": 688.42},
    {"UNB_Codigo": "11531", "Razao_Social": "JOSE WILLAME DE ARAUJO", "Nota": "204.550", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 2453.82, "Devolucao": 0.0, "Valor_Liquido": 2453.82},
    {"UNB_Codigo": "11522", "Razao_Social": "MARCONDES FERREIRA ALVES 03", "Nota": "204.551", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 592.50, "Devolucao": 0.0, "Valor_Liquido": 592.50},
    {"UNB_Codigo": "16670", "Razao_Social": "PANIFICADORA E POUSADA SOUS", "Nota": "204.552", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS", "Valor_Nota": 838.08, "Devolucao": 0.0, "Valor_Liquido": 838.08},
    {"UNB_Codigo": "16670", "Razao_Social": "PANIFICADORA E POUSADA SOUS", "Nota": "204.553", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS", "Valor_Nota": 178.70, "Devolucao": 0.0, "Valor_Liquido": 178.70},
    {"UNB_Codigo": "11541", "Razao_Social": "AMAILDO COLACO DINIZ", "Nota": "204.554", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 161.70, "Devolucao": 0.0, "Valor_Liquido": 161.70},
    {"UNB_Codigo": "11541", "Razao_Social": "AMAILDO COLACO DINIZ", "Nota": "204.554", "Sit": "003", "Op": "2", "Condicao_Pagto": "BONIFICACAO", "Valor_Nota": 22.50, "Devolucao": 0.0, "Valor_Liquido": 22.50},
    {"UNB_Codigo": "11514", "Razao_Social": "MANUEL ANTONIO DOS SANTOS", "Nota": "204.555", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 117.00, "Devolucao": 0.0, "Valor_Liquido": 117.00},
    {"UNB_Codigo": "14464", "Razao_Social": "JOSE JARKSON", "Nota": "204.556", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 504.68, "Devolucao": 0.0, "Valor_Liquido": 504.68},
    {"UNB_Codigo": "15941", "Razao_Social": "ADEILSON FIDELIS MATIAS 082", "Nota": "204.557", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 631.00, "Devolucao": 0.0, "Valor_Liquido": 631.00},
    {"UNB_Codigo": "13976", "Razao_Social": "ALTERANO GOMES DE OLIVEIRA", "Nota": "204.558", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 647.74, "Devolucao": 0.0, "Valor_Liquido": 647.74},
    {"UNB_Codigo": "12672", "Razao_Social": "JOSUE SILVA FIDELIS", "Nota": "204.559", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 2 DIAS", "Valor_Nota": 280.51, "Devolucao": 0.0, "Valor_Liquido": 280.51},
    {"UNB_Codigo": "12689", "Razao_Social": "ELIZABETE ARAUJO PEREIRA", "Nota": "204.560", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 408.95, "Devolucao": 0.0, "Valor_Liquido": 408.95},
    {"UNB_Codigo": "12689", "Razao_Social": "ELIZABETE ARAUJO PEREIRA", "Nota": "204.561", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 1969.07, "Devolucao": 0.0, "Valor_Liquido": 1969.07},
    {"UNB_Codigo": "11544", "Razao_Social": "MARINA SOARES OLIVEIRA", "Nota": "204.562", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 128.74, "Devolucao": 0.0, "Valor_Liquido": 128.74},
    {"UNB_Codigo": "11521", "Razao_Social": "ROSENILDO DA SILVA BATISTA", "Nota": "204.563", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 4 DIAS", "Valor_Nota": 357.47, "Devolucao": 0.0, "Valor_Liquido": 357.47},
    {"UNB_Codigo": "11521", "Razao_Social": "ROSENILDO DA SILVA BATISTA", "Nota": "204.564", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 4 DIAS", "Valor_Nota": 252.85, "Devolucao": 0.0, "Valor_Liquido": 252.85},
    {"UNB_Codigo": "17102", "Razao_Social": "54.447.822 WANNESSA DE SOUZ", "Nota": "204.565", "Sit": "003", "Op": "1", "Condicao_Pagto": "BOLETO 5 DIAS", "Valor_Nota": 469.73, "Devolucao": 0.0, "Valor_Liquido": 469.73},
    {"UNB_Codigo": "19309", "Razao_Social": "JOSE ROBERIO MATIAS ARAUJO", "Nota": "204.566", "Sit": "003", "Op": "1", "Condicao_Pagto": "CREDITO EM CONTAS", "Valor_Nota": 131.70, "Devolucao": 0.0, "Valor_Liquido": 131.70},
]

# Section 2: Vasilhame
vasilhame_data = [
    {"Codigo": "27983", "Un": "un", "Denominacao": "GFA VIDRO 635ML,AMBAR,TIPO A,RET", "Preco": 1.20, "Saida_Qtde": "1.224/00", "Saida_Valor": 1468.80, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "1.224/00-", "Diferenca_Valor": -1468.80},
    {"Codigo": "37108", "Un": "pc", "Denominacao": "CHAPATEX,1,00 M,1,20 M,0,03 M,", "Preco": 8.00, "Saida_Qtde": "6/00", "Saida_Valor": 48.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "6/00-", "Diferenca_Valor": -48.00},
    {"Codigo": "42069", "Un": "pc", "Denominacao": "PALETE MADEIRA,1,05 M,1,25 M,0,1", "Preco": 40.00, "Saida_Qtde": "6/00", "Saida_Valor": 240.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "6/00-", "Diferenca_Valor": -240.00},
    {"Codigo": "104195", "Un": "pc", "Denominacao": "PALETE MADEIRA,1,00 M,1,20 M,0,1", "Preco": 40.00, "Saida_Qtde": "6/00", "Saida_Valor": 240.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "6/00-", "Diferenca_Valor": -240.00},
    {"Codigo": "188005", "Un": "un", "Denominacao": "GARRAFEIRA PLAST,12 GFA 1L,AMBEV", "Preco": 40.00, "Saida_Qtde": "52/00", "Saida_Valor": 2080.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "52/00-", "Diferenca_Valor": -2080.00},
    {"Codigo": "188006", "Un": "un", "Denominacao": "GFA VIDRO 1L,AMBAR,RETORN.,,", "Preco": 1.66, "Saida_Qtde": "624/00", "Saida_Valor": 1035.84, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "624/00-", "Diferenca_Valor": -1035.84},
    {"Codigo": "198214", "Un": "un", "Denominacao": "GFA VIDRO 330ML,AMBAR,TIPO S GP,", "Preco": 1.00, "Saida_Qtde": "3.174/00", "Saida_Valor": 3174.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "3.174/00-", "Diferenca_Valor": -3174.00},
    {"Codigo": "786238", "Un": "un", "Denominacao": "GFA VIDRO 635ML,VERDE,TIPO A,RET", "Preco": 1.85, "Saida_Qtde": "24/00", "Saida_Valor": 44.40, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "24/00-", "Diferenca_Valor": -44.40},
    {"Codigo": "863059", "Un": "pc", "Denominacao": "GARRAFEIRA PLAST PRETA 23 GARRAF", "Preco": 40.00, "Saida_Qtde": "139/00", "Saida_Valor": 5560.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "139/00-", "Diferenca_Valor": -5560.00},
    {"Codigo": "899599", "Un": "pc", "Denominacao": "GARRAFEIRA PLAST,24 GFA 600ML,,,", "Preco": 40.00, "Saida_Qtde": "52/00", "Saida_Valor": 2080.00, "Retorno_Qtde": "/00", "Retorno_Valor": 0.00, "Diferenca_Qtde": "52/00-", "Diferenca_Valor": -2080.00},
]

# Section 3: Resumo Financeiro
resumo_data = [
    {"Tipo_Pagamento": "CREDITO EM CONTA", "Saida": 35732.09, "Retorno": 0.0},
    {"Tipo_Pagamento": "BLOQUETO BANCARIO", "Saida": 15274.88, "Retorno": 0.0},
    {"Tipo_Pagamento": "BONIFICACAO", "Saida": 1098.91, "Retorno": 0.0},
    {"Tipo_Pagamento": "COMODATO", "Saida": 4500.00, "Retorno": 0.0},
    {"Tipo_Pagamento": "TROCA", "Saida": 84.89, "Retorno": 0.0},
    {"Tipo_Pagamento": "* SIMPLES REMESSA", "Saida": 108.30, "Retorno": 0.0},
]

df_notas = pd.DataFrame(notas_data)
df_vasilhame = pd.DataFrame(vasilhame_data)
df_resumo = pd.DataFrame(resumo_data)

out_dir = Path(r"c:\Users\cadcom.patos\Documents\promax-web-driver\data")
out_dir.mkdir(exist_ok=True)

df_notas.to_csv(out_dir / "prestacao_contas_notas.csv", index=False, sep=";", encoding="utf-8-sig")
df_vasilhame.to_csv(out_dir / "prestacao_contas_vasilhame.csv", index=False, sep=";", encoding="utf-8-sig")
df_resumo.to_csv(out_dir / "prestacao_contas_resumo.csv", index=False, sep=";", encoding="utf-8-sig")

# Excel file with sheets
with pd.ExcelWriter(out_dir / "prestacao_contas_mapa_94036.xlsx", engine="openpyxl") as writer:
    df_notas.to_excel(writer, sheet_name="Notas", index=False)
    df_vasilhame.to_excel(writer, sheet_name="Vasilhame", index=False)
    df_resumo.to_excel(writer, sheet_name="Resumo_Financeiro", index=False)

print("CSV and XLSX generated successfully in data/")
