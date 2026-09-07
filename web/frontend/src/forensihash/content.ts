export type PublicFeatureStatus = 'AVAILABLE' | 'IN_DEVELOPMENT' | 'PLANNED'

export interface ForensiHashFeature {
  id: string
  name: string
  description: string
  status: PublicFeatureStatus
  scope: string
  limitation?: string
  evidence: readonly string[]
}

export interface ForensiHashCorrelation {
  id: string
  name: string
  compares: string
  observes: string
  doesNotMean: string
  evidence: readonly string[]
}

export interface ForensiHashRoadmapItem {
  id: string
  name: string
  description: string
  status: PublicFeatureStatus
  evidence: readonly string[]
}

export interface ForensiHashWorkflowStep { id: string; name: string; description: string }
export interface ForensiHashLimitation { id: string; text: string }
export interface ForensiHashEfficiencyMetric { id: string; name: string; description: string }

export interface EfficiencyStudy {
  id: string
  version: string
  sampleSize: number
  taskType: string
  caseComplexity: string
  baselineTimeMinutes: number
  fhTimeMinutes: number
  medianReduction: number
  range: readonly [number, number]
  methodology: string
  limitations: readonly string[]
  publishedAt: string
}

export const FEATURE_STATUS_LABELS: Record<PublicFeatureStatus, string> = {
  AVAILABLE: 'Disponível', IN_DEVELOPMENT: 'Em desenvolvimento', PLANNED: 'Planejado',
}

export const workflowSteps: readonly ForensiHashWorkflowStep[] = [
  { id: 'case-files', name: 'Arquivos do Caso', description: 'O conjunto fornecido pelo examinador permanece identificado por arquivo.' },
  { id: 'specialized-reading', name: 'Leitura especializada', description: 'Engines e parsers compatíveis examinam bytes, estrutura, texto e campos disponíveis.' },
  { id: 'facts', name: 'Fatos técnicos + proveniência', description: 'Observações são normalizadas sem apagar sua origem ou seu valor bruto.' },
  { id: 'correlation', name: 'Correlação determinística', description: 'Regras comparam somente elementos tecnicamente compatíveis.' },
  { id: 'relations', name: 'Relações e resultados', description: 'Correspondências, divergências e limitações permanecem separadas.' },
  { id: 'review', name: 'Revisão pelo perito', description: 'O profissional confere contexto, significado e alcance de cada observação.' },
]

export const productFeatures: readonly ForensiHashFeature[] = [
  { id: 'hashes', name: 'Hashes e integridade de cópia', status: 'AVAILABLE', description: 'Calcula hashes por leitura incremental e acompanha a aquisição da cópia de trabalho.', scope: 'MD5, SHA-1, SHA-224, SHA-256, SHA-384 e SHA-512; SHA-256 também integra a verificação da cópia de trabalho.', limitation: 'Correspondência de hash demonstra igualdade dos bytes comparados, não autenticidade, autoria ou validade jurídica.', evidence: ['app/engines/hash_engine.py', 'app/evidence/acquisition.py', 'tests/test_hash_engine_io.py'] },
  { id: 'format-structure', name: 'Formato e estrutura', status: 'AVAILABLE', description: 'Compara extensão e assinatura binária e aplica inspeção estrutural conforme o formato reconhecido.', scope: 'Magic number, estrutura PDF, parser PDF raw e observações binárias limitadas.', limitation: 'Marcadores, assinaturas internas, múltiplos EOF ou bytes após EOF são observações estruturais isoladas.', evidence: ['app/engines/magic_number_engine.py', 'app/engines/pdf_structure_engine.py', 'app/binary/parsers/pdf_raw_parser.py'] },
  { id: 'metadata', name: 'Metadados de documentos e imagens', status: 'AVAILABLE', description: 'Extrai campos técnicos disponíveis, incluindo XMP e EXIF quando presentes e suportados.', scope: 'Creator, Producer, datas, software, EXIF, GPS e outros campos retornados pela ferramenta configurada.', limitation: 'A extração ampla depende do ExifTool; metadados podem estar ausentes, incompletos ou ter sido alterados.', evidence: ['app/engines/metadata_engine.py', 'app/rules/gps_rule.py', 'tests/test_jpeg_desktop_integration.py'] },
  { id: 'text-ocr', name: 'Texto nativo e OCR', status: 'AVAILABLE', description: 'Extrai texto de PDFs e aplica OCR a PDFs ou imagens suportadas quando necessário.', scope: 'Segmentos mantêm método de extração e página quando essa informação está disponível.', limitation: 'OCR depende da qualidade do material e de Tesseract/Poppler disponíveis no ambiente.', evidence: ['app/services/text_extraction_service.py', 'tests/test_correlation_v2_1_providers.py'] },
  { id: 'signatures', name: 'Assinaturas PDF e certificados', status: 'IN_DEVELOPMENT', description: 'Identifica estruturas de assinatura PDF e organiza os campos disponíveis de cada assinatura e certificado.', scope: 'Já disponível para registros independentes, SigningTime, timestamp confiável quando presente e intervalo declarado do certificado.', limitation: 'A cobertura atual é estrutural e não equivale a validação criptográfica completa.', evidence: ['app/digital_signature/parsers/pdf_parser.py', 'tests/test_signature_collection_model_v1.py'] },
  { id: 'timeline', name: 'Timeline técnica', status: 'AVAILABLE', description: 'Organiza observações temporais de fontes diferentes sem convertê-las no mesmo tipo de evento.', scope: 'Preserva precisão, estado de timezone, fonte, papel temporal e intervalos de certificado quando disponíveis.', limitation: 'Ordenação temporal não reconstrói, por si só, a verdade dos fatos.', evidence: ['app/services/timeline_service.py', 'tests/test_timeline_ux_v2.py'] },
  { id: 'structured', name: 'JSON e arquivos ZIP', status: 'AVAILABLE', description: 'Processa JSON, JSONL e NDJSON suportados e inspeciona arquivos ZIP com limites defensivos.', scope: 'Campos JSON mantêm caminho estruturado; ZIP é inspecionado sem materializar caminhos de entrada.', limitation: 'O parser JSON profundo usa o módulo Rust opcional; não há parser genérico completo de logs, XML ou OpenXML.', evidence: ['app/services/json_parser_service.py', 'app/parsers/archive.py', 'tests/test_archive_inspection.py'] },
  { id: 'entities-ip', name: 'Identificadores e IPs', status: 'AVAILABLE', description: 'Extrai e normaliza entidades suportadas e endereços IPv4/IPv6 com referência à ocorrência.', scope: 'CPF, telefone, IP, e-mail, valores monetários e datas quando a validação e o contexto sustentam a classificação.', limitation: 'Contexto externo de IP é opcional e aproximado; mesmo IP não individualiza pessoa ou dispositivo.', evidence: ['app/entities', 'app/services/ip_extraction_service.py', 'tests/test_entity_extraction_v2.py'] },
  { id: 'case-correlation', name: 'Correlação do Caso', status: 'AVAILABLE', description: 'Indexa fatos e ocorrências de múltiplos artefatos e executa regras determinísticas rastreáveis.', scope: 'Evidence Graph factual, índice do Caso, relações canônicas e resultados versionados.', limitation: 'Igualdade, coocorrência ou proximidade não estabelecem causalidade, autoria ou relevância jurídica.', evidence: ['app/correlation/v2', 'tests/test_canonical_fact_pipeline_v1.py', 'tests/test_evidence_graph_correlation_v2.py'] },
  { id: 'comparison', name: 'Comparação entre arquivos', status: 'AVAILABLE', description: 'Compara um par selecionado e apresenta correspondências técnicas entre seus resultados.', scope: 'A seleção do par e os resultados permanecem vinculados aos artefatos escolhidos.', limitation: 'Uma correspondência isolada não estabelece derivação ou origem.', evidence: ['app/engines/comparison_engine.py', 'app/services/comparison_service.py', 'tests/test_comparison_workspace.py'] },
  { id: 'deep-explorer', name: 'Deep File Explorer', status: 'AVAILABLE', description: 'Permite navegar estruturas suportadas e abrir visualizações técnicas e hexadecimais limitadas.', scope: 'PDF e JPEG possuem a cobertura profunda atualmente testada; a leitura HEX é paginada e limitada.', limitation: 'A profundidade varia por formato e o núcleo Rust é opcional.', evidence: ['app/pages/deep_file_explorer_page.py', 'tests/test_deep_file_explorer_ui_v1.py', 'tests/test_hex_grid_widget.py'] },
]

export const caseCorrelations: readonly ForensiHashCorrelation[] = [
  { id: 'identical-sha256', name: 'SHA-256 calculado entre artefatos', compares: 'SHA-256 calculado diretamente dos bytes de artefatos distintos.', observes: 'Conteúdo binariamente idêntico entre os arquivos comparados.', doesNotMean: 'Que os arquivos são autênticos, válidos, contemporâneos ou produzidos pela mesma pessoa.', evidence: ['app/correlation/v2/pipeline.py::IdenticalCalculatedHashRule', 'tests/test_canonical_fact_pipeline_v1.py'] },
  { id: 'declared-hash', name: 'Hash declarado × hash calculado', compares: 'Uma declaração estruturada vinculada de forma inequívoca a um artefato e o hash calculado desse alvo.', observes: 'Correspondência ou diferença entre valores do mesmo algoritmo.', doesNotMean: 'Que o documento é autêntico, juridicamente válido ou foi produzido por determinada pessoa.', evidence: ['app/correlation/v2/pipeline.py::DeclaredHashVerificationRule', 'tests/test_declared_hash_verification_rule_v1.py'] },
  { id: 'signing-validity', name: 'SigningTime × intervalo do certificado', compares: 'O SigningTime declarado pela assinatura e os limites NotBefore/NotAfter do certificado vinculado.', observes: 'Se os instantes comparáveis estão dentro ou fora do intervalo declarado.', doesNotMean: 'Que a assinatura é criptograficamente válida, que o relógio é confiável ou que a pessoa assinou naquele instante.', evidence: ['app/correlation/v2/pipeline.py::SigningTimeCertificateValidityRule', 'tests/test_signing_time_certificate_validity_rule_v1.py'] },
  { id: 'document-metadata-date', name: 'Data documental × metadados', compares: 'Uma data documental selecionada pelo pipeline e campos temporais de metadados do mesmo artefato.', observes: 'Relação anterior, posterior, coincidente ou sobreposta dentro da precisão disponível.', doesNotMean: 'Que o metadado representa criação material, alteração efetiva, pactuação ou origem comprovada.', evidence: ['app/correlation/v2/pipeline.py::DocumentDateMetadataTemporalRule', 'tests/test_document_date_metadata_temporal_rule_v1.py'] },
  { id: 'same-fact', name: 'Mesmo identificador observado em mais de um artefato', compares: 'Fatos do mesmo tipo e valor normalizado, com cada ocorrência e origem preservadas.', observes: 'Recorrência factual do valor nos arquivos do Caso.', doesNotMean: 'Identidade de pessoa, causalidade, autoria, relevância ou vínculo material entre os artefatos.', evidence: ['app/correlation/v2/engine.py::EvidenceGraphCorrelationEngine', 'tests/test_correlation_v2_1_providers.py'] },
]

export const efficiencyPillars = [
  ['Menos alternância entre ferramentas', 'Reúne etapas compatíveis em um fluxo técnico único.'],
  ['Menos busca manual por relações', 'Indexa ocorrências e aplica comparações determinísticas suportadas.'],
  ['Menos reconstrução de cronologia', 'Organiza datas, precisão, timezone e origem em uma Timeline comum.'],
  ['Menos retrabalho de organização', 'Mantém resultados, limitações e referências ligados ao Caso.'],
] as const

export const efficiencyMetrics: readonly ForensiHashEfficiencyMetric[] = [
  { id: 'total', name: 'Tempo total', description: 'Do início do fluxo equivalente até a entrega técnica definida no protocolo.' },
  { id: 'preparation', name: 'Preparação', description: 'Organização do conjunto e configuração das ferramentas necessárias.' },
  { id: 'extraction', name: 'Extração', description: 'Hashes, metadados, texto e estruturas dentro do mesmo escopo.' },
  { id: 'correlation', name: 'Correlação', description: 'Conferência cruzada e busca de relações previamente definidas.' },
  { id: 'organization', name: 'Organização', description: 'Consolidação de datas, observações, fontes e limitações.' },
  { id: 'quality', name: 'Retrabalho e omissões', description: 'Repetições e itens detectáveis omitidos no protocolo de referência.' },
]

export const limitations: readonly ForensiHashLimitation[] = [
  { id: 'formats', text: 'Nem todos os formatos possuem a mesma profundidade de suporte.' },
  { id: 'optional-tools', text: 'ExifTool, Tesseract, Poppler e o núcleo Rust são componentes opcionais; sua ausência limita etapas específicas.' },
  { id: 'ocr', text: 'OCR depende da legibilidade, resolução, idioma e qualidade do material.' },
  { id: 'metadata', text: 'Metadados podem estar ausentes, incompletos ou alterados e exigem interpretação contextual.' },
  { id: 'time', text: 'Timestamps preservam a precisão e o timezone disponíveis; domínios incompatíveis não são comparados por suposição.' },
  { id: 'signature', text: 'Estrutura de assinatura e intervalo de certificado não equivalem a validação criptográfica completa.' },
  { id: 'correlation', text: 'Correlação não equivale a causalidade, autoria, autenticidade, fraude ou conclusão pericial.' },
  { id: 'absence', text: 'Dados ausentes permanecem ausentes: ausência de entrada não é convertida em divergência.' },
  { id: 'scale', text: 'Grandes lotes ainda exigem medição e evolução de cache, memória e desempenho operacional.' },
]

export const roadmapItems: readonly ForensiHashRoadmapItem[] = [
  { id: 'canonical', name: 'Pipeline e correlações canônicas', status: 'AVAILABLE', description: 'Facts, ocorrências, proveniência, índice do Caso e regras determinísticas versionadas.', evidence: ['docs/architecture/CANONICAL_EVIDENCE_PIPELINE_V1.md'] },
  { id: 'timeline-explorer', name: 'Timeline e explorador de correlações', status: 'AVAILABLE', description: 'Visualizações do desktop consomem resultados canônicos e preservam referências técnicas.', evidence: ['docs/architecture/DESKTOP_IA_TIMELINE_V2_AUDIT.md', 'docs/architecture/CASE_CORRELATION_EXPLORER_V1_AUDIT.md'] },
  { id: 'rules', name: 'Ampliação de regras determinísticas', status: 'IN_DEVELOPMENT', description: 'Novas relações somente entram no produto quando houver comparabilidade e proveniência suficientes.', evidence: ['README.md::Evolução planejada'] },
  { id: 'provenance-pdf', name: 'Proveniência navegável mais profunda em PDF', status: 'IN_DEVELOPMENT', description: 'Aprofundar caminhos entre páginas, recursos, objetos e metadados suportados.', evidence: ['README.md::PDF Structural Engine'] },
  { id: 'parsers', name: 'Parsers adicionais', status: 'PLANNED', description: 'Expandir suporte estruturado para OpenXML, XML e formatos de log.', evidence: ['README.md::Evolução planejada'] },
  { id: 'carving', name: 'Carving com limites e cadeia de derivação', status: 'PLANNED', description: 'Recuperação controlada de regiões somente com proveniência e limites explícitos.', evidence: ['AGENTS.md::Escopo futuro', 'README.md::Evolução planejada'] },
  { id: 'triage', name: 'Triagem analítica explicável', status: 'PLANNED', description: 'Priorização opcional após extração determinística; não classifica fraude nem define relevância jurídica.', evidence: ['docs/architecture/ml/ML_RULES.md'] },
  { id: 'scale-export', name: 'Escala, cache e exportação técnica', status: 'PLANNED', description: 'Medir gargalos, evoluir lotes maiores e ampliar snapshots e quadros técnicos.', evidence: ['docs/audits/FORENSIHASH_REPOSITORY_HEALTH_AUDIT.md', 'README.md::Evolução planejada'] },
]

// Nenhum estudo é publicado até existir protocolo, amostra e resultado revisados.
export const publishedEfficiencyStudies: readonly EfficiencyStudy[] = []
