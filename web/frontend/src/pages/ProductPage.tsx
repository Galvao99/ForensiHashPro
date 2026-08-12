import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'

const audiences = [
  ['PERITOS', 'Extração, correlação, timeline e rastreabilidade para apoiar fundamentação pericial baseada em fatos técnicos.'],
  ['ADVOGADOS', 'Compreensão de artefatos, limitações probatórias e elementos apresentados para apoiar quesitos e leitura técnica objetiva.'],
  ['AUDITORIA / COMPLIANCE', 'Revisão de artefatos, consistência de registros, comparação entre fontes e documentação de divergências técnicas.'],
  ['EQUIPES TÉCNICAS', 'Inspeção estruturada de hashes, metadados, formatos, parsers, eventos e relações entre arquivos.'],
]

const capabilityGroups = [
  ['IDENTIDADE', ['Hashes', 'Magic number / tipo real', 'MIME e identidade binária']],
  ['ESTRUTURA', ['Estrutura PDF', 'Revisões incrementais', 'ZIP / archive inspection', 'Estrutura binária']],
  ['CONTEÚDO', ['Texto nativo', 'OCR', 'JSON estruturado', 'Relatórios biométricos suportados']],
  ['CONTEXTO', ['IP', 'CPF e telefone', 'Datas e valores', 'Entidades normalizadas']],
  ['RELAÇÕES', ['Analysis Sets', 'Hash declarado', 'Source divergence', 'Comparação entre arquivos']],
  ['TEMPO', ['Timeline técnica', 'Datas de metadados', 'Eventos estruturais', 'Eventos de fontes relacionadas']],
]

const analysisSteps = [
  ['01', 'Identificação', 'Determina identidade binária, tipo real e características iniciais do artefato.'],
  ['02', 'Extração', 'Coleta metadados, texto e elementos estruturados disponíveis.'],
  ['03', 'Estrutura', 'Inspeciona a organização interna compatível com o formato reconhecido.'],
  ['04', 'Entidades', 'Resolve elementos como IPs, documentos, telefones, datas e valores com proveniência.'],
  ['05', 'Timeline', 'Organiza eventos temporais e estruturais sem inventar datas ausentes.'],
  ['06', 'Correlação', 'Relaciona elementos semanticamente comparáveis entre fontes e arquivos.'],
  ['07', 'Resultado técnico', 'Apresenta fatos, warnings, limitações e referências à evidência associada.'],
]

const limitations = ['autoria', 'fraude ou intenção', 'autenticidade material', 'validade jurídica', 'identidade biométrica sem mecanismo específico adequado', 'eventos ou fontes que não foram fornecidos']

export function ProductPage() {
  return (
    <article className="forensi-product">
      <DocumentMetadata title="ForensiHash | Análise de Artefatos Digitais — ARQEN" description="Conheça o ForensiHash, plataforma de análise técnica de arquivos digitais com hashes, metadados, timeline, correlação, estrutura e rastreabilidade." />

      <Section className="forensi-hero" eyebrow="FORENSIHASH · DIGITAL ANALYSIS" title="Análise técnica de artefatos digitais." headingLevel="h1">
        <p className="lead">Uma ferramenta para inspeção, correlação e reconstrução técnica de evidências digitais, com foco em rastreabilidade, integridade e reprodutibilidade.</p>
        <div className="hero-actions"><a className="button-link button-light" href="#capacidades">Explorar capacidades</a><a className="text-link text-link--light" href="#como-funciona">Entender uma análise ↓</a></div>
        <div className="forensi-signal" aria-hidden="true"><span>HASH</span><i /><span>STRUCTURE</span><i /><span>CONTEXT</span><i /><span>RESULT</span></div>
      </Section>

      <Section className="arqen-section" eyebrow="APLICAÇÃO" title="Para quem o ForensiHash foi pensado">
        <p className="lead">Para profissionais que precisam compreender o que os artefatos tecnicamente demonstram, sem substituir a avaliação pericial, jurídica ou institucional.</p>
        <div className="forensi-audience-grid">{audiences.map(([title, text], index) => <article key={title}><span>0{index + 1}</span><h3>{title}</h3><p>{text}</p></article>)}</div>
      </Section>

      <Section id="capacidades" className="arqen-section forensi-dark-section" eyebrow="CAPACIDADES REAIS" title="O que ele analisa">
        <p className="lead">Os módulos organizam observações por função. A disponibilidade concreta depende do tipo de artefato, das integrações presentes no ambiente e do material fornecido.</p>
        <div className="capability-groups">{capabilityGroups.map(([group, items], index) => <article key={group as string}><span>0{index + 1}</span><h3>{group}</h3><ul>{(items as string[]).map(item => <li key={item}>{item}</li>)}</ul></article>)}</div>
      </Section>

      <Section id="como-funciona" className="arqen-section analysis-flow-section" eyebrow="FLUXO DIDÁTICO" title="Como funciona uma análise">
        <div className="analysis-flow"><strong>ARQUIVO</strong>{analysisSteps.map(([number, title, text]) => <article key={number}><span>{number}</span><div><h3>{title}</h3><p>{text}</p></div></article>)}</div>
      </Section>

      <Section className="arqen-section practical-section" eyebrow="EXEMPLO FICTÍCIO" title="Três fontes. Uma leitura técnica organizada.">
        <p className="lead">Um conjunto didático formado por <code>contrato.pdf</code>, <code>selfie.jpg</code> e <code>logs.json</code>.</p>
        <div className="artifact-example">
          <article><strong>contrato.pdf</strong><span>SHA-256</span><span>Producer</span><span>CreationDate</span><span>2 incremental updates</span></article>
          <article><strong>selfie.jpg</strong><span>SHA-256</span><span>metadata disponível</span><span>identidade binária</span></article>
          <article><strong>logs.json</strong><span>IP observado</span><span>user-agent</span><span>timestamp</span><span>event IDs</span></article>
          <div className="example-correlation"><strong>CORRELAÇÃO</strong><p>hash declarado: <b>MATCH</b></p><p>IP presente em log: <b>CORRESPONDÊNCIA</b></p><p>datas entre fontes: <b>WARNING / DIVERGÊNCIA</b></p><p>timeline: <b>ESTRUTURADA</b></p></div>
        </div>
        <p className="institutional-note">Correspondências e divergências são fatos técnicos contextualizados. Este exemplo não determina fraude, autoria ou validade.</p>
      </Section>

      <Section className="arqen-section warning-section" eyebrow="WARNINGS EXPLICÁVEIS" title="Da observação ao detalhe verificável.">
        <div className="warning-layout"><div><p className="lead">Warnings destacam fatos que merecem revisão e mantêm regra, valores, origem, contexto e limitações disponíveis para inspeção.</p><p>O ForensiHash não converte um warning em conclusão automática.</p></div><details className="warning-card"><summary><span aria-hidden="true">△</span><strong>ModifyDate anterior a CreationDate</strong><small>Ver detalhes</small></summary><dl><div><dt>REGRA</dt><dd>ordem temporal declarada</dd></div><div><dt>VALOR A</dt><dd>ModifyDate · valor da fonte</dd></div><div><dt>VALOR B</dt><dd>CreationDate · valor da fonte</dd></div><div><dt>ORIGEM</dt><dd>metadados do artefato</dd></div><div><dt>CONTEXTO</dt><dd>campos declarados pelo produtor</dd></div><div><dt>LIMITAÇÃO</dt><dd>datas declaradas não demonstram, isoladamente, a história material do arquivo</dd></div></dl></details></div>
      </Section>

      <Section className="arqen-section forensi-dark-section" eyebrow="TIMELINE" title="Tempo declarado e estrutura observável não são a mesma coisa.">
        <div className="technical-timeline" role="img" aria-label="Timeline didática com eventos temporais e estruturais"><article><span>T0</span><strong>arquivo criado</strong><small>evento temporal declarado</small></article><article><span>T1</span><strong>metadata</strong><small>referência temporal da fonte</small></article><article><span>T2</span><strong>assinatura</strong><small>informação disponível no artefato</small></article><article><span>T3</span><strong>incremental update</strong><small>evento estrutural · timestamp pode ser desconhecido</small></article><article><span>T4</span><strong>evento de log</strong><small>fonte externa relacionada</small></article></div>
        <p className="lead">Eventos temporais carregam referências de tempo dentro das garantias de sua fonte. Eventos estruturais podem demonstrar ordem ou revisão sem possuir timestamp conhecido.</p>
      </Section>

      <Section className="arqen-section correlation-section" eyebrow="ANALYSIS SET · CORRELATION V2" title="Relações entre arquivos, com comparabilidade explícita.">
        <div className="correlation-map" role="img" aria-label="Contrato, selfie e logs relacionados por uma análise de correlação"><div><code>contrato.pdf</code><code>selfie.jpg</code><code>logs.json</code></div><b aria-hidden="true">→</b><strong>CORRELATION</strong><b aria-hidden="true">→</b><ul><li>CPF match</li><li>IP match</li><li>hash embutido match</li><li>divergência OCR / nativo</li><li>arquivos binariamente idênticos</li><li>hash declarado sem artefato correspondente</li></ul></div>
        <p>Mismatch só é apresentado quando os elementos são semanticamente comparáveis. Divergência documenta uma diferença entre fontes; não constitui, automaticamente, suspeita ou conclusão.</p>
      </Section>

      <Section className="arqen-section contracting-section" eyebrow="EXEMPLO DE APLICAÇÃO" title="Contratação eletrônica">
        <div className="contracting-grid"><div><p className="lead">Um PDF final isolado pode não conter toda a história da contratação.</p><p>ForensiHash ajuda a organizar e comparar o material que foi efetivamente disponibilizado.</p></div><div className="contracting-elements">{['contrato', 'selfie', 'documentos', 'logs', 'IP', 'user-agent', 'timestamps', 'hashes', 'assinaturas', 'eventos', 'estrutura PDF'].map(item => <span key={item}>{item}</span>)}</div></div>
        <p>Peritos, advogados e equipes técnicas podem examinar as fontes entregues, suas correspondências, divergências e limitações sem presumir eventos ausentes.</p>
      </Section>

      <Section className="arqen-section limits-section" eyebrow="LIMITES" title="O que o ForensiHash não decide">
        <div className="limits-grid">{limitations.map(item => <div key={item}><span aria-hidden="true">×</span><p>{item}</p></div>)}</div>
        <p className="forensi-statement">A ferramenta organiza evidência técnica. A interpretação permanece dependente do contexto e do profissional responsável.</p>
      </Section>

      <Section className="arqen-section ecosystem-section" eyebrow="ARQEN · PAPÉIS DISTINTOS" title="Preservação e análise podem se complementar.">
        <div className="product-bridge" role="img" aria-label="DDNA preserva o estado e ForensiHash analisa o estado"><article><strong>DDNA</strong><span>preserva o estado</span><small>proveniência · custódia</small></article><div><span>artefato</span><i aria-hidden="true">↓</i><span>evidence package</span></div><article><strong>FORENSIHASH</strong><span>analisa o estado</span><small>inspeção · correlação</small></article></div>
        <p>Os produtos têm responsabilidades distintas e não precisam ser usados em conjunto em todos os cenários.</p>
      </Section>

      <Section className="arqen-section forensi-final-cta" eyebrow="FORENSIHASH" title="Analise artefatos digitais com mais contexto.">
        <div className="hero-actions"><Link className="button-link button-light" to="/app/analysis">Acessar plataforma</Link><Link className="text-link text-link--light" to="/ddna">Conhecer DDNA <span aria-hidden="true">↗</span></Link></div>
      </Section>
    </article>
  )
}
