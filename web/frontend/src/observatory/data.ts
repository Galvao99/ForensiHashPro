import type { ObservatoryArticle, RegulatoryItem, ResearchSource, ResearchStatus, StateResearch, ResearchCoverage } from './models'
import { validateStateResearch, validateUniqueIds } from './models'

const source = (id: string, title: string, organization: string, url: string): ResearchSource => ({ id, title, organization, url, sourceType: 'COURT_REGISTRY', accessedAt: '2026-09-05', jurisdiction: 'Brasil' })

export const cnjResolution233: ResearchSource = { id:'cnj-resolution-233-2016', title:'Resolução CNJ nº 233, de 13 de julho de 2016', organization:'Conselho Nacional de Justiça', url:'https://atos.cnj.jus.br/atos/detalhar/2310', sourceType:'CNJ_ACT', publishedAt:'2016-07-13', accessedAt:'2026-09-05', jurisdiction:'Brasil', description:'Dispõe sobre o cadastro de profissionais e órgãos técnicos ou científicos na Justiça de primeiro e segundo graus.' }

const courtSources = {
  RJ: source('tjrj-public-experts','Lista de peritos','Tribunal de Justiça do Estado do Rio de Janeiro','https://www.tjrj.jus.br/servicos/peritos/lista-de-peritos'),
  SE: source('tjse-public-experts','Peritos','Tribunal de Justiça do Estado de Sergipe','https://www.tjse.jus.br/portal/servicos/judiciais/peritos'),
  PI: source('tjpi-public-experts','Cadastro de peritos','Tribunal de Justiça do Estado do Piauí','https://www.tjpi.jus.br/portaltjpi/servicos/cadastro-de-peritos/'),
  AP: source('tjap-public-experts','Lista pública de peritos','Tribunal de Justiça do Estado do Amapá','https://sig.tjap.jus.br/sgpe_grid_peritos/sgpe_grid_peritos.php'),
  PA: source('tjpa-public-experts','Peritos cadastrados','Tribunal de Justiça do Estado do Pará','https://apps.tjpa.jus.br/capjus/peritos-cadastrados'),
  TO: source('tjto-public-experts','Relação de profissionais credenciados e peritos cadastrados','Corregedoria-Geral da Justiça do Tocantins','https://corregedoria.tjto.jus.br/component/content/article/corregedoria-geral-da-justica-disponibiliza-relacao-de-profissionais-credenciados-e-peritos-cadastrados-em-seu-portal?catid=8&layout=blog'),
  RR: source('tjrr-public-experts','Credenciamentos — Cadastro Eletrônico de Peritos','Tribunal de Justiça do Estado de Roraima','https://www.tjrr.jus.br/index.php/credenciamentos-subalc'),
  PR: source('tjpr-caju','Cadastro de Auxiliares da Justiça','Tribunal de Justiça do Estado do Paraná','https://portal.tjpr.jus.br/caju/publico/credencial/perito.do?tjpr.url.crypto=8a6c53f8698c7ff7d88bd1d17bac0727d751336abc0458fc1ba0bb4c6e9b4853'),
}

const names: Record<string,string> = { AC:'Acre',AL:'Alagoas',AP:'Amapá',AM:'Amazonas',BA:'Bahia',CE:'Ceará',DF:'Distrito Federal',ES:'Espírito Santo',GO:'Goiás',MA:'Maranhão',MT:'Mato Grosso',MS:'Mato Grosso do Sul',MG:'Minas Gerais',PA:'Pará',PB:'Paraíba',PR:'Paraná',PE:'Pernambuco',PI:'Piauí',RJ:'Rio de Janeiro',RN:'Rio Grande do Norte',RS:'Rio Grande do Sul',RO:'Rondônia',RR:'Roraima',SC:'Santa Catarina',SP:'São Paulo',SE:'Sergipe',TO:'Tocantins' }
type StateSeed = Partial<StateResearch> & { status?: ResearchStatus; coverage?: ResearchCoverage }
const researched: Record<string,StateSeed> = {
  RJ:{tribunal:'TJRJ',status:'COMPLETED',coverage:'INTEGRAL_DEDUPLICATED',sourceRecordsCount:12165,uniqueProfessionalsCount:10804,digitalCoreCount:187,digitalRankingComparable:true,notes:'Core previamente classificado na base deduplicada do tribunal.',sources:[courtSources.RJ]},
  SE:{tribunal:'TJSE',status:'COMPLETED',coverage:'INTEGRAL',sourceRecordsCount:1999,digitalCoreCount:45,digitalRankingComparable:true,notes:'Levantamento integral com classificação do núcleo digital/TI.',sources:[courtSources.SE]},
  PI:{tribunal:'TJPI',status:'PARTIAL',coverage:'TERM_BASED_SUBSET',researchedSubsetUniqueCount:374,digitalCoreCount:51,digitalRankingComparable:true,notes:'Recorte por termos; não representa o cadastro integral.',sources:[courtSources.PI]},
  AP:{tribunal:'TJAP',status:'COMPLETED',coverage:'INTEGRAL_DEDUPLICATED',uniqueProfessionalsCount:352,digitalCoreCount:11,digitalRankingComparable:true,notes:'Lista pública integral deduplicada.',sources:[courtSources.AP]},
  PA:{tribunal:'TJPA',status:'COMPLETED',coverage:'PUBLIC_LIST_DEDUPLICATED',sourceRecordsCount:918,uniqueProfessionalsCount:577,digitalCoreCount:10,digitalRankingComparable:true,notes:'577 profissionais únicos identificados entre 918 linhas públicas.',sources:[courtSources.PA]},
  TO:{tribunal:'TJTO',status:'PARTIAL',coverage:'EXACT_CORE_TYPES',sourceRecordsCount:5272,digitalCoreCount:116,digitalRankingComparable:true,notes:'Tipos exatos Analista de TI + Forense; forte outlier de densidade. A base geral observada não é tratada como total nacionalmente comparável de pessoas.',sources:[courtSources.TO]},
  RR:{tribunal:'TJRR',status:'PARTIAL',coverage:'SUBSET',researchedSubsetUniqueCount:13,digitalCoreCount:13,digitalRankingComparable:true,notes:'Pessoas únicas no recorte; não representa o cadastro integral.',sources:[courtSources.RR]},
  AL:{tribunal:'TJAL',status:'PARTIAL',coverage:'COLLECTION_INTERRUPTED',notes:'Portal oficial confirmado; extração interrompida na rodada anterior.'},
  BA:{tribunal:'TJBA',status:'IN_RESEARCH',coverage:'SOURCE_CONFIRMED',notes:'Fonte pública oficial confirmada; sem quantitativo consolidado.'},
  CE:{tribunal:'TJCE',status:'IN_RESEARCH',coverage:'SOURCE_CONFIRMED',notes:'Sistema CPTEC confirmado; lista pública agregada exportável não localizada.'},
  MA:{tribunal:'TJMA',status:'PARTIAL',coverage:'RESTRICTED_ACCESS',notes:'Sistema confirmado; acesso principal restrito por autenticação.'},
  PB:{tribunal:'TJPB',status:'PARTIAL',coverage:'FILTERED_QUERY',notes:'Consulta pública requer filtros; não há agregado consolidado.'},
  PE:{tribunal:'TJPE',status:'PARTIAL',coverage:'SOURCE_UNAVAILABLE',notes:'Fonte oficial confirmada; endpoint público indisponível durante a coleta.'},
  RN:{tribunal:'TJRN',status:'IN_RESEARCH',coverage:'SOURCE_CONFIRMED',notes:'Fonte pública confirmada; sem resultado quantitativo consolidado.'},
  PR:{tribunal:'TJPR',status:'PARTIAL',coverage:'CREDENTIALS_ONLY',credentialSpecialtyCount:35373,notes:'35.373 credenciais/especialidades observadas. Uma mesma pessoa pode possuir múltiplas credenciais.',sources:[courtSources.PR]},
  SC:{tribunal:'TJSC',status:'IN_RESEARCH',coverage:'SOURCE_CONFIRMED',notes:'Sistema confirmado; total público agregado não localizado.'},
  RS:{tribunal:'TJRS',status:'PARTIAL',coverage:'TAXONOMY_ONLY',notes:'Taxonomia e categorias observadas; nomes e contagens não foram consolidados com confiabilidade.'},
}

export const stateResearch: StateResearch[] = Object.entries(names).map(([uf,stateName]) => ({ uf,stateName,status:'NOT_STARTED',methodologyVersion:'v1.1',coverage:'NOT_LOCATED',sources:[],limitations:['A presença no cadastro não implica atuação efetiva, disponibilidade atual ou número de nomeações.'],...researched[uf] }))
export const regulatoryItems: RegulatoryItem[] = [{id:'cnj-resolution-233',slug:'resolucao-cnj-233-cadastro-peritos',title:'Resolução CNJ nº 233 estrutura cadastro de profissionais e órgãos técnicos',summary:'A norma disciplina a criação e a manutenção de cadastros eletrônicos no âmbito da Justiça de primeiro e segundo graus.',category:'CNJ',organization:'Conselho Nacional de Justiça',publishedAt:'2016-07-13',status:'ALTERADO',relevance:'É uma referência normativa central para delimitar o objeto e as fontes da pesquisa sobre cadastros judiciais.',sources:[cnjResolution233],tags:['cadastro','CPTEC','perícia judicial']}]
export const observatoryArticles: ObservatoryArticle[] = []
stateResearch.forEach(validateStateResearch)
validateUniqueIds([...Object.values(courtSources),cnjResolution233])
validateUniqueIds(regulatoryItems)
