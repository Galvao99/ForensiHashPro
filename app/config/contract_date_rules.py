DATE_CLASSIFICATION_RULES = {
    "Pactuação": {
        "score": 100,
        "patterns": [
            r"data\s+da\s+contrata[cç][aã]o",
            r"contrata[cç][aã]o",
            r"pactua[cç][aã]o",
            r"pactuad[oa]",
            r"celebrad[oa]",
            r"celebra[cç][aã]o",
            r"formaliza[cç][aã]o",
            r"formalizad[oa]",
            r"contrato\s+celebrad[oa]",
            r"instrumento\s+celebrad[oa]",
        ],
    },
    "Assinatura textual": {
        "score": 80,
        "patterns": [
            r"assinatura",
            r"assinado\s+eletronicamente",
            r"assinado\s+digitalmente",
            r"assinado\s+em",
            r"data\s+da\s+assinatura",
        ],
    },
    "Aceite": {
        "score": 70,
        "patterns": [
            r"aceite",
            r"aceito",
            r"aceita[cç][aã]o",
            r"clique\s+em\s+aceitar",
            r"bot[aã]o\s+aceitar",
        ],
    },
    "Emissão": {
        "score": 35,
        "patterns": [
            r"data\s+de\s+emiss[aã]o",
            r"emitido\s+em",
            r"emiss[aã]o",
        ],
    },
    "Ignorar": {
        "score": -200,
        "patterns": [
            r"vencimento",
            r"parcela",
            r"nascimento",
            r"validade",
            r"expira[cç][aã]o",
            r"prazo",
            r"boleto",
            r"fatura",
            r"pagamento",
            r"venc\.",
            r"cpf",
            r"rg",
        ],
    },
}