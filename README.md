<p align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PySide6](https://img.shields.io/badge/PySide6-Qt6-success)
![Status](https://img.shields.io/badge/status-Beta-orange)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-Proprietary-red)

<div align="center">

# 🔍 ForensiHash Pro

### Plataforma de Análise e Correlação Forense de Documentos Digitais

Análise técnica de documentos eletrônicos com foco em **integridade**, **rastreabilidade**, **autenticidade** e **correlação de vestígios digitais**.

> ⚠️ Projeto em desenvolvimento (Beta)

</div>

---

# Sobre

O **ForensiHash Pro** é uma ferramenta desktop desenvolvida em **Python + PySide6**, voltada para análise pericial de documentos digitais.

Seu objetivo é centralizar diversas verificações técnicas normalmente realizadas em ferramentas distintas, permitindo uma análise rápida, organizada e reproduzível.

Entre os principais recursos estão:

- cálculo de hashes
- análise de metadados
- verificação de assinaturas digitais
- identificação de produtores de PDF
- timeline técnica
- OCR
- correlação automática de vestígios
- análise de IP
- comparação entre arquivos

A ferramenta foi projetada principalmente para auxiliar análises envolvendo:

- contratos eletrônicos
- documentos PDF
- fotografias
- imagens
- evidências digitais

---

# Funcionalidades

## Integridade

- ✅ Hash MD5
- ✅ SHA-1
- ✅ SHA-224
- ✅ SHA-256
- ✅ SHA-384
- ✅ SHA-512

Em desenvolvimento:

- CRC32
- BLAKE2
- BLAKE3
- SHA3
- Whirlpool

---

## Magic Number

Identificação do tipo real do arquivo independentemente da extensão.

Suporte atual:

- PDF
- JPEG
- PNG
- GIF
- BMP
- ZIP
- RAR
- 7Z

---

## Metadados

Extração automática utilizando ExifTool.

Exemplos:

- Producer
- Creator
- CreateDate
- ModifyDate
- Software
- GPS
- Device
- EXIF

---

## Assinatura Digital

Análise completa de assinaturas digitais em PDFs.

Informações:

- certificado
- emissor
- cadeia
- validade
- ICP-Brasil
- algoritmo
- resumo criptográfico

Em evolução para visual semelhante ao Xolido.

---

## OCR

Extração automática de texto.

Suporte:

- PDFs
- imagens

Planejado:

- OCR multilíngue
- busca inteligente
- localização do texto

---

## Timeline Técnica

Construção automática de eventos como:

- criação
- modificação
- assinatura
- datas contratuais
- eventos correlacionados

---

## Vestígios 2.0

Motor próprio de correlação.

Detecta automaticamente:

- datas incompatíveis
- hashes mencionados no documento
- reutilização de arquivos
- inconsistências
- relações entre evidências

---

## Contexto de IP

Consulta inteligente de IPs.

Atualmente:

- IPv4
- IPv6
- IP privado
- Loopback
- Reservado
- Geolocalização
- ASN
- ISP

Planejado:

- VPN
- Proxy
- Tor
- Datacenter
- Score de fraude
- WHOIS

---

## Comparação

Comparação entre múltiplos documentos.

Itens comparados:

- Hashes
- Magic Number
- Metadados
- Assinaturas
- Vestígios

---

# Arquitetura

```
ForensiHashPro

├── app
│
├── engines
│   ├── hash
│   ├── metadata
│   ├── magic number
│   ├── assinatura
│   ├── findings
│
├── investigation
│   ├── correlation engine
│   ├── rules
│
├── integrations
│   ├── ip
│
├── pages
│
├── widgets
│
├── services
│
├── widgets/

tests/
```

---

# Tecnologias

- 📄 Geral
- 🔐 Hashes
- 📑 Metadados
- ⚠ Vestígios
- 🕒 Timeline
- 🧬 Magic Number
- 🔏 Assinatura Digital
- 📄 OCR
- 📊 Comparação Forense
- 📍 Contexto técnico de IP
- 📱 Análise de relatórios biométricos JSON
- 🧱 Estrutura Binária
- 🤖 Correlação de Evidências

---

Planejado:

- Rust
- YARA
- libmagic
- SQLite

## Ambiente suportado

- Versão principal e garantida nesta fase: **Python 3.12**.
- Python 3.14 foi usado em uma execução de auditoria, mas não é suportado nem
  garantido porque parte das wheels instaladas não declarou compatibilidade.
- O núcleo Rust opcional requer Rust/Cargo e maturin para desenvolvimento.

## Instalação e configuração local

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Copie `config/settings.example.json` para `config/settings.json` somente se
precisar alterar opções locais. O arquivo local é ignorado pelo Git. A chave da
IP2Location deve ser fornecida exclusivamente pelo ambiente:

```powershell
$env:IP2LOCATION_ENABLED = "true"
$env:IP2LOCATION_API_KEY = "<valor-fornecido-localmente>"
```

O ForensiHash não carrega `.env` automaticamente. `.env.example` serve apenas
como catálogo de variáveis e nunca deve conter valores reais.

Ferramentas externas:

- ExifTool: autodetectado no bundle ou no `PATH`; caminho configurável por
  `FORENSIHASH_EXIFTOOL_PATH`.
- Tesseract: não é instalado pelo pip; caminho configurável por
  `FORENSIHASH_TESSERACT_PATH`.
- Poppler (`pdftoppm`): exigido pelo OCR de PDF e não instalado pelo pip;
  diretório configurável por `FORENSIHASH_POPPLER_PATH`.
- Os recursos podem ser desabilitados pelas variáveis documentadas em
  `.env.example`. Estados ausente, desabilitado e caminho inválido são distintos.

---

# Objetivos do Projeto

O projeto busca oferecer uma plataforma única para análise técnica de documentos digitais, reduzindo a necessidade de utilizar diversas ferramentas separadas.

A proposta é reunir em um único ambiente funcionalidades como:

- análise estrutural
- integridade
- autenticação
- metadados
- OCR
- timeline
- correlação automática
- investigação

---

# Roadmap

## Beta

- [x] Hashes
- [x] Metadados
- [x] Magic Number
- [x] OCR
- [x] Timeline
- [x] Assinatura Digital
- [x] Contexto de IP
- [x] Correlação
- [ ] Dashboard Inicial
- [ ] Parser Hex
- [ ] Exportação PDF
- [ ] Melhorias de UX

---

## V1

- 🔍 Hex Viewer
- 🗺 Timeline Inteligente
- 📑 Snapshot para Laudos
- 📄 Exportação PDF
- 🧠 Temporal Consistency Engine

---

## Futuro

- [ ] IA para interpretação técnica
- [ ] Sistema Antifraude
- [ ] Banco de indicadores
- [ ] Regras customizadas
- [ ] Plugins
- [ ] Cloud Sync

---

# Licença

Este projeto encontra-se em desenvolvimento.

A definição da licença ocorrerá após o lançamento da versão Beta.

---

# Aviso

O ForensiHash Pro é uma ferramenta de apoio à análise técnica.

Os resultados produzidos representam vestígios e informações técnicas que devem ser interpretados em conjunto com os demais elementos disponíveis em cada caso concreto.

A ferramenta não substitui a análise pericial.

---

<div align="center">

Desenvolvido por Rodrigo Galvão

</div>
