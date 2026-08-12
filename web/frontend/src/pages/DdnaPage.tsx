import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { BranchDiagram, FlowDiagram, LedgerDiagram } from '../components/DdnaDiagram'
import { Section } from '../components/ui'
import { ddnaReferences } from '../content/ddnaReferences'

const verifyChecks = [
  ['Artifact SHA-256', 'MATCH'], ['Manifest integrity', 'VALID'], ['CAdES', 'VALID'],
  ['Timestamp', 'VALID'], ['Technical fingerprint', 'MATCH'], ['Custody chain', 'VALID'],
]

function ExternalLink({ href }: { href: string }) {
  return <a className="source-link" href={href} target="_blank" rel="noopener noreferrer">Ver fonte <span aria-hidden="true">↗</span></a>
}

export function DdnaPage() {
  return <article className="ddna-page">
    <DocumentMetadata title="DDNA | Custódia e Proveniência Digital — ARQEN" description="Conheça a arquitetura DDNA em desenvolvimento para preservação, rastreabilidade e verificação de artefatos digitais." />
    <Section className="ddna-hero" eyebrow="DDNA · RESEARCH / DEVELOPMENT" title="CUSTÓDIA VERIFICÁVEL PARA ARTEFATOS DIGITAIS." headingLevel="h1">
      <span className="development-flag">PRODUTO EM DESENVOLVIMENTO</span>
      <p className="lead">Uma arquitetura em desenvolvimento para registrar, preservar e posteriormente verificar o estado técnico de arquivos digitais a partir de um marco de custódia.</p>
      <div className="hero-actions"><a className="button-link" href="#como-funciona">Entenda como funciona</a><a className="text-link" href="#t0">Conheça o T0 ↓</a></div>
      <p className="institutional-note">O desenho apresentado pode evoluir durante validação, testes e estudos normativos. Esta página descreve uma proposta técnica — não um serviço de custódia disponível.</p>
    </Section>

    <Section id="problema" eyebrow="O PROBLEMA" title="UM ARQUIVO NASCE HOJE. COMO DEMONSTRAR SEU ESTADO ANOS DEPOIS?">
      <div className="ddna-question-grid">{['Este é exatamente o mesmo arquivo?', 'Ele foi alterado?', 'Quem o recebeu e quando?', 'Quais metadados existiam?', 'Como entrou em custódia?', 'Um terceiro consegue verificar?'].map(question => <blockquote key={question}>“{question}”</blockquote>)}</div>
      <FlowDiagram label="Ciclo de circulação de um arquivo ao longo do tempo" nodes={['ARQUIVO HOJE', 'e-mail · nuvem · GED', 'cópias · conversões', 'sistemas · processos', <strong>ANOS DEPOIS: É O MESMO?</strong>]} compact />
      <p className="lead">O desafio não é apenas armazenar. Arquivos circulam entre plataformas, integrações, exportações e processos. Preservar identidade binária, estado técnico, aquisição e histórico de manuseio pode tornar a verificação posterior mais objetiva.</p>
    </Section>

    <Section className="surface-section" eyebrow="IDENTIDADE BINÁRIA" title="HASH É FUNDAMENTAL — MAS NÃO É TODA A CADEIA.">
      <div className="ddna-hash-comparison">
        <FlowDiagram label="Hash identifica os bytes do arquivo" nodes={['ARQUIVO', 'SHA-256', <strong>IDENTIDADE BINÁRIA</strong>]} compact />
        <div className="ddna-manifest-map" role="img" aria-label="Registro DDNA reúne hash, formato, metadados, estrutura, aquisição, contexto, manifesto, assinatura, timestamp e custódia">
          <strong>DDNA RECORD</strong>{['hash', 'formato', 'metadados', 'estrutura', 'aquisição', 'contexto', 'manifesto', 'assinatura', 'timestamp', 'custódia'].map(item => <span key={item}>{item}</span>)}
        </div>
      </div>
      <p>O hash permite detectar mudança nos bytes. Isoladamente, ele não documenta quem calculou, quando, em qual contexto, qual sistema operou, como o registro foi preservado ou qual estado técnico foi observado.</p>
    </Section>

    <Section id="t0" eyebrow="T0 · CUSTODY GENESIS POINT" title="O MARCO EM QUE O ARTEFATO ENTRA EM CUSTÓDIA DDNA.">
      <div className="ddna-t0-grid">
        <FlowDiagram label="Limite temporal do T0" nodes={[<><small>ANTES DO T0</small><br />? → ? → ? → arquivo</>, <strong className="t0-node">T0 · DDNA ACQUISITION</strong>, 'hash · metadata · structure', 'manifest · CAdES · timestamp', 'T1 → T2 → T3 → T4']} />
        <div><p className="lead"><strong>Antes do T0:</strong> a proposta não afirma integridade histórica.</p><p className="lead"><strong>Depois do T0:</strong> busca preservar um registro verificável do estado observado e dos eventos de custódia.</p><aside className="ddna-boundary">O DDNA não pretende provar o que aconteceu antes do T0.</aside></div>
      </div>
    </Section>

    <Section className="surface-section" eyebrow="T0 INTEGRADO" title="MAIS PRÓXIMO DO EVENTO QUE PRODUZ OU RECEBE O ARTEFATO.">
      <FlowDiagram label="T0 integrado ao sistema de contratação" nodes={['CLIENTE CONCLUI FLUXO', 'SISTEMA GERA ARQUIVO FINAL', 'DDNA AGENT / API', <strong>T0</strong>, 'ARMAZENAMENTO INSTITUCIONAL']} compact />
      <div className="ddna-time-example"><code>14:32:07.381</code><span>arquivo finalizado</span><code>14:32:07.429</code><span>DDNA acquisition</span><strong>Δ = 48 ms</strong></div>
      <p className="institutional-note">Exemplo exclusivamente didático, não um benchmark. Integração automática busca reduzir a janela entre geração/recebimento e custódia.</p>
    </Section>

    <Section id="como-funciona" eyebrow="REGISTRO TÉCNICO" title="ARTEFATO E CONTEXTO, SEM CONFUNDIR SUAS ORIGENS.">
      <BranchDiagram label="Separação entre registro do artefato e contexto do fluxo" leftTitle="ARTIFACT" left={['hash', 'size', 'MIME / magic', 'metadata', 'structure', 'signatures']} rightTitle="CONTEXT" right={['transaction_id', 'session_id', 'observed IP', 'user-agent', 'channel', 'source system']} footer={<>MANIFEST → CAdES → TIMESTAMP</>} />
      <p>O <strong>Artifact Record</strong> descreve o que é observável no arquivo. O <strong>Context Record</strong> descreve dados objetivamente observados pelo fluxo. Contexto é específico de cada perfil; o núcleo de custódia busca permanecer universal.</p>
    </Section>

    <Section className="surface-section" eyebrow="QUALQUER SEQUÊNCIA DE BYTES" title="PRESERVAÇÃO NÃO DEVE DEPENDER APENAS DA EXTENSÃO.">
      <div className="ddna-format-grid">{[['UNKNOWN FILE', 'hash + size + magic + T0'], ['PDF', '+ estrutura PDF'], ['JPEG', '+ EXIF / metadata'], ['DOCX', '+ OpenXML'], ['JSON', '+ campos estruturados']].map(([type, enrichment]) => <article key={type}><strong>{type}</strong><span>↓</span><p>{enrichment}</p></article>)}</div>
      <p>Quando um formato é reconhecido, a arquitetura pode enriquecer o registro. Estes exemplos expressam o desenho proposto e não uma promessa de suporte funcional atual do DDNA.</p>
    </Section>

    <Section eyebrow="ORIGINAL INTACTO" title="A PROVA É EXTERNA AO ARQUIVO PRESERVADO.">
      <div className="ddna-original-grid"><div className="ddna-file-stack"><code>contrato.pdf</code><code>contrato.ddna.json</code><code>contrato.ddna.p7s</code><code>contrato.ddna.tsr</code></div><FlowDiagram label="Manifesto, assinatura CAdES destacada e timestamp" nodes={['ARQUIVO → SHA-256', 'EXTRAÇÃO TÉCNICA', 'MANIFEST + CANONICALIZAÇÃO', 'DIGEST', 'CAdES DETACHED', 'TRUSTED TIMESTAMP']} compact /></div>
      <p>O arquivo original permanece intacto. O manifesto referencia seu hash e pode ser protegido por assinatura CAdES destacada. A assinatura protege o registro assinado; não estabelece automaticamente a veracidade material do conteúdo. O formato final do pacote permanece em definição.</p>
      <FlowDiagram label="Relação entre CAdES, manifesto, hash e arquivo" nodes={[<strong>CAdES</strong>, 'MANIFEST', 'SHA-256', 'ARQUIVO']} compact />
    </Section>

    <Section id="verify" className="surface-section ddna-verify-section" eyebrow="DDNA VERIFY" title="E DAQUI A 5 OU 10 ANOS?">
      <div className="ddna-verify-grid"><FlowDiagram label="Verificação futura de um pacote DDNA" nodes={['arquivo + manifest + .p7s + timestamp', <strong>DDNA VERIFY</strong>, 'recalcular hash', 'validar manifesto / assinatura / timestamp', 'comparar estado técnico', <strong>RESULTADO DISCRIMINADO</strong>]} /><div className="ddna-checks" aria-label="Exemplo didático de resultados específicos">{verifyChecks.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div></div>
      <p>O resultado deve indicar exatamente o que foi validado, o que divergiu e o que não pôde ser determinado — sem condensar verificações distintas em um rótulo genérico.</p>
    </Section>

    <Section eyebrow="VERIFICAÇÃO INDEPENDENTE" title="CONFIANÇA NÃO DEVE DEPENDER DE ‘ACREDITAR NA DDNA’.">
      <FlowDiagram label="Pacote verificável por diferentes implementações" nodes={['DDNA CRIA REGISTRO', 'EVIDENCE PACKAGE', <div className="ddna-parallel"><span>DDNA Verify</span><span>ForensiHash</span><span>implementação futura independente</span></div>]} compact />
      <p className="lead">A visão é publicar artefatos e especificação suficientes para validação independente e offline. O formato e a especificação ainda estão em desenvolvimento.</p>
    </Section>

    <Section className="surface-section" eyebrow="PERFIL · CONTRATAÇÃO ELETRÔNICA" title="O FLUXO PODE ENVOLVER MUITO MAIS QUE O PDF FINAL.">
      <div className="ddna-evidence-set" role="img" aria-label="Conjunto de evidências de uma contratação eletrônica"><div>{['contrato.pdf', 'selfie.jpg', 'documento-frente.jpg', 'documento-verso.jpg', 'biometric.json', 'logs.json', 'context'].map(item => <code key={item}>{item}</code>)}</div><span aria-hidden="true">→</span><strong>DDNA EVIDENCE SET</strong></div>
      <p>Cada artefato conserva hash, estado e <code>evidence_ref</code> próprios. O conjunto pode relacioná-los por <code>transaction_id</code>, contexto, manifesto, assinatura e timestamp. Trata-se de um perfil possível, não do único propósito do DDNA.</p>
      <div className="ddna-two-cards"><article><h3>SELFIE: PRESERVAÇÃO, NÃO BIOMETRIA</h3><FlowDiagram label="Verificação por hash de uma selfie" nodes={['selfie.jpg', 'SHA-256 + T0', 'selfie apresentada depois', 'novo SHA-256', <strong>MATCH / MISMATCH</strong>]} compact /><p>Isso não afirma quem aparece na fotografia. Demonstra apenas se os bytes apresentados correspondem ao artefato registrado no T0.</p></article><article><h3>IP: SNAPSHOT CONTEXTUAL</h3><FlowDiagram label="Snapshot contextual de IP observado" nodes={['OBSERVED IP · 189.x.x.x', 'consulta contemporânea', 'ASN · ISP · prefix · country', 'region / city estimate', 'source · dataset/version · lookup time']} compact /><p>Geolocalização é uma estimativa fornecida pela fonte consultada naquele momento, nunca localização exata. Bases mudam; preservar fonte, versão e instante permite contextualizar o que ela informou.</p></article></div>
    </Section>

    <Section eyebrow="CUSTODY LEDGER" title="EVENTOS DE MANUSEIO EXPLÍCITOS E ENCADEADOS.">
      <LedgerDiagram />
      <div className="ddna-ledger-fields">{['event_id', 'custody_id', 'timestamp', 'actor', 'action', 'reason', 'artifact_hash', 'previous_event_hash', 'signature'].map(field => <code key={field}>{field}</code>)}</div>
      <FlowDiagram label="Encadeamento criptográfico de eventos de custódia" nodes={['E0', 'E1 + H(E0)', 'E2 + H(E1)', 'E3 + H(E2)']} compact />
      <p>O hash do evento anterior pode tornar alterações no histórico detectáveis. Encadeamento criptográfico não exige blockchain.</p>
    </Section>

    <Section className="surface-section" eyebrow="LIMITES" title="O QUE O DDNA NÃO É — E O QUE BUSCA SER.">
      <div className="ddna-do-dont"><article><h3>DDNA NÃO É</h3>{['detector automático de fraude', 'biometria', 'antivírus', 'decisor da validade de contratos', 'prova de eventos anteriores ao T0', 'substituto do trabalho pericial'].map(item => <p key={item}><span aria-hidden="true">×</span>{item}</p>)}</article><article><h3>DDNA BUSCA SER</h3>{['infraestrutura de custódia', 'registro do estado técnico', 'preservação de proveniência', 'histórico verificável', 'camada de confiança integrável', 'mecanismo de verificação futura'].map(item => <p key={item}><span aria-hidden="true">✓</span>{item}</p>)}</article></div>
    </Section>

    <Section eyebrow="UM ECOSSISTEMA, PAPÉIS DISTINTOS" title="DDNA PRESERVA. FORENSIHASH ANALISA.">
      <BranchDiagram label="Papéis distintos de DDNA e ForensiHash" leftTitle="DDNA" left={['custody', 'preservation', 'provenance', 'integrity']} rightTitle="FORENSIHASH" right={['analysis', 'interpretation', 'correlations', 'timeline']} footer={<strong>VERIFY</strong>} />
      <p className="ddna-statement">DDNA registra o estado. ForensiHash investiga o que esse estado revela.</p>
    </Section>

    <Section className="surface-section" eyebrow="ROADMAP · CONTEXT INTELLIGENCE" title="RELAÇÕES HISTÓRICAS, EM CAMADA FUTURA E SEPARADA.">
      <FlowDiagram label="Context Engine futuro" nodes={['HISTORICAL DDNA RECORDS', 'CONTEXT ENGINE', 'RELATIONSHIP ANALYSIS', 'INDICATORS']} compact />
      <div className="ddna-tag-list">{['mesmo hash em identidades distintas', 'dispositivo em múltiplos CPFs', 'nomes divergentes', 'telefone reutilizado', 'IP / ASN recorrente', 'infraestrutura de datacenter'].map(item => <span key={item}>{item}</span>)}</div>
      <p>Roadmap de análise de relações, anomalias e continuidade/divergência histórica. Não integra o núcleo de custódia e não produz, por si, conclusão sobre fraude.</p>
    </Section>

    <Section eyebrow="CONTEXTO TÉCNICO E JURÍDICO" title="POR QUE INTEGRIDADE E CADEIA DE CUSTÓDIA IMPORTAM?">
      <p className="lead">As fontes abaixo demonstram que preservação, mesmidade, auditabilidade e exame independente são problemas reconhecidos. Elas não certificam, homologam, recomendam ou tornam o DDNA obrigatório.</p>
      <div className="ddna-foundation-grid">{ddnaReferences.slice(0, 6).map(reference => <article key={reference.id} id={reference.id}><span>{reference.institution} · {reference.date}</span><h3>{reference.title}</h3><p>{reference.summary}</p><ExternalLink href={reference.href} /></article>)}</div>
    </Section>

    <Section className="surface-section" eyebrow="REFERÊNCIAS INTERNACIONAIS" title="ISO/IEC 27037, 27041, 27042 E 27043.">
      <p>A arquitetura pretende ser estudada e mapeada frente a estas referências. Isso não representa certificação ISO.</p>
      <div className="ddna-iso-grid">{ddnaReferences.filter(item => item.id.startsWith('iso-')).map(reference => <article key={reference.id}><span>{reference.institution} · {reference.date}</span><h3>{reference.title}</h3><p>{reference.summary}</p><ExternalLink href={reference.href} /></article>)}</div>
    </Section>

    <Section eyebrow="ICP-BRASIL · ITI" title="ASSINATURAS, CERTIFICADOS, CAdES E TEMPO CONFIÁVEL.">
      <div className="ddna-two-cards">{ddnaReferences.filter(item => ['icp-brasil', 'validar-iti'].includes(item.id)).map(reference => <article key={reference.id}><h3>{reference.title}</h3><p>{reference.summary}</p><ExternalLink href={reference.href} /></article>)}</div>
      <p>CAdES e carimbo do tempo podem compor a estratégia criptográfica proposta. A arquitetura DDNA não está apresentada como credenciada ou homologada pelo ITI ou pela ICP-Brasil.</p>
    </Section>

    <Section className="surface-section" eyebrow="PRIVACIDADE" title="CUSTÓDIA NÃO ELIMINA OBRIGAÇÕES DE PROTEÇÃO DE DADOS.">
      <p className="lead">Documentos, selfies, logs, IPs e identificadores podem envolver dados pessoais. Finalidade, minimização, retenção, segurança, direitos dos titulares e governança devem orientar o desenho futuro.</p>
      <ExternalLink href={ddnaReferences.find(item => item.id === 'lgpd')!.href} />
    </Section>

    <Section eyebrow="REFERÊNCIAS E LEITURAS" title="FONTES PRIMÁRIAS CONSULTADAS.">
      <div className="reference-list">{ddnaReferences.map(reference => <article key={reference.id}><div><span>{reference.institution} · {reference.date}</span><h2>{reference.title}</h2><p>{reference.summary}</p></div><ExternalLink href={reference.href} /></article>)}</div>
    </Section>

    <Section className="surface-section ddna-status" eyebrow="STATUS" title="ARQUITETURA EM PESQUISA E DESENVOLVIMENTO.">
      <p className="lead">Manifesto, perfil de contexto, CAdES destacada, timestamp, ledger, pacote e especificação de verificação ainda exigem implementação, testes, revisão de segurança e estudos normativos.</p>
      <div className="hero-actions"><a className="text-link" href="#t0">Rever o T0 ↑</a><Link className="button-link button-secondary" to="/forensihash">Conhecer o ForensiHash</Link></div>
    </Section>
  </article>
}
