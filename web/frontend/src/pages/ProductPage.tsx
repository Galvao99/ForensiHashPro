import { Link } from 'react-router-dom'
import { DocumentMetadata } from '../components/DocumentMetadata'
import { Section } from '../components/ui'
import {
  FEATURE_STATUS_LABELS, caseCorrelations, efficiencyMetrics, efficiencyPillars,
  limitations, productFeatures, publishedEfficiencyStudies, roadmapItems,
  workflowSteps, type PublicFeatureStatus,
} from '../forensihash/content'

const statusOrder: readonly PublicFeatureStatus[] = ['AVAILABLE', 'IN_DEVELOPMENT', 'PLANNED']

export function ProductPage() {
  return (
    <article className="forensi-product">
      <DocumentMetadata title="ForensiHash | Análise e correlação de evidências — ARQEN" description="Plataforma desktop de análise técnica e correlação de evidências presentes em arquivos digitais, com proveniência e revisão pelo perito." />

      <Section className="forensi-hero forensi-hero-v2" eyebrow="FORENSIHASH · DESKTOP · EM DESENVOLVIMENTO" title="Da análise isolada de arquivos à correlação técnica do Caso." headingLevel="h1">
        <p className="lead">Uma plataforma desktop para examinar arquivos digitais, estruturar fatos técnicos e identificar relações entre evidências com proveniência e rastreabilidade.</p>
        <div className="forensi-hero-badges" aria-label="Características do ForensiHash">{['Desktop', 'Análise técnica', 'Correlação de evidências', 'Pesquisa e desenvolvimento'].map(item => <span key={item}>{item}</span>)}</div>
        <div className="hero-actions"><a className="button-link button-light" href="#como-funciona">Ver como funciona</a><a className="text-link text-link--light" href="#funcionalidades">Explorar funcionalidades ↓</a></div>
        <p className="forensi-hero-note">O ForensiHash organiza evidência técnica. Não decide fraude, autenticidade, autoria ou validade jurídica.</p>
      </Section>

      <Section className="arqen-section forensi-positioning" eyebrow="POSICIONAMENTO" title="Análise técnica e correlação, em um fluxo rastreável.">
        <p className="lead">O ForensiHash reduz trabalho técnico repetitivo ao organizar análise, extração e correlação de informações presentes nos arquivos de um Caso, preservando a rastreabilidade e a autonomia do perito.</p>
        <div className="forensi-problem-grid">
          <div><span>UM CASO PODE REUNIR</span><p>PDFs, imagens, JSON, logs, CSV, protocolos, arquivos compactados, documentos assinados e outros artefatos relacionados.</p></div>
          <div><span>O TRABALHO MANUAL</span><p>Pode exigir ferramentas diferentes para hashes, metadados, texto, assinaturas, datas, comparações e organização de achados.</p></div>
          <div><span>O PAPEL DO FH</span><p>Concentrar etapas compatíveis e tornar relações técnicas revisáveis, sem substituir interpretação, conferência ou redação pericial.</p></div>
        </div>
      </Section>

      <Section id="como-funciona" className="arqen-section forensi-workflow-section" eyebrow="COMO FUNCIONA" title="Do arquivo à revisão profissional.">
        <p className="lead">Parsers especializados produzem observações. O pipeline canônico mantém fatos, ocorrências e proveniência separados antes de executar regras determinísticas.</p>
        <ol className="forensi-workflow" aria-label="Fluxo técnico do ForensiHash">{workflowSteps.map((step, index) => <li key={step.id}><span>{String(index + 1).padStart(2, '0')}</span><div><h3>{step.name}</h3><p>{step.description}</p></div></li>)}</ol>
        <p className="institutional-note">Um resultado técnico é mais útil quando o perito consegue retornar à sua origem.</p>
      </Section>

      <Section id="funcionalidades" className="arqen-section forensi-dark-section" eyebrow="CAPACIDADES AUDITADAS" title="O que o ForensiHash analisa hoje.">
        <p className="lead">“Disponível” indica código integrado e testado dentro do escopo descrito — não cobertura ilimitada de formato, ambiente ou contexto.</p>
        <div className="forensi-feature-grid">{productFeatures.map(feature => <article key={feature.id}>
          <div className="forensi-card-heading"><h3>{feature.name}</h3><span className={`feature-status feature-status--${feature.status.toLowerCase()}`}>{FEATURE_STATUS_LABELS[feature.status]}</span></div>
          <p>{feature.description}</p><dl><div><dt>Escopo</dt><dd>{feature.scope}</dd></div>{feature.limitation && <div><dt>Limitação</dt><dd>{feature.limitation}</dd></div>}</dl>
        </article>)}</div>
      </Section>

      <Section id="correlacoes" className="arqen-section forensi-correlation-section" eyebrow="CORRELAÇÃO DO CASO" title="Relações somente quando há suporte técnico.">
        <p className="lead">O ForensiHash não apenas apresenta dados por arquivo: o pipeline canônico relaciona fatos comparáveis entre artefatos e conserva a trilha até cada ocorrência.</p>
        <div className="forensi-correlation-grid">{caseCorrelations.map(correlation => <article key={correlation.id}><h3>{correlation.name}</h3><dl><div><dt>O que compara</dt><dd>{correlation.compares}</dd></div><div><dt>Pode observar</dt><dd>{correlation.observes}</dd></div><div><dt>Não significa</dt><dd>{correlation.doesNotMean}</dd></div></dl></article>)}</div>
        <div className="neutrality-strip" aria-label="Princípios de neutralidade técnica"><span>correlação ≠ causalidade</span><span>frequência ≠ relevância</span><span>proximidade ≠ origem</span><span>mesmo IP ≠ mesma pessoa</span></div>
      </Section>

      <Section className="arqen-section forensi-interface-section" eyebrow="INTERFACE REAL" title="O Caso em duas perspectivas complementares.">
        <p className="lead">Capturas reais da interface desktop com dados sintéticos de teste. Elas documentam recursos existentes, não simulam funcionalidades futuras.</p>
        <div className="forensi-screenshot-grid">
          <figure><img src="/assets/forensihash-correlation-explorer.png" alt="Explorador de correlações do ForensiHash mostrando hashes, CPF e produtor observados em múltiplos artefatos" loading="lazy" /><figcaption><strong>Explorador de correlações</strong><span>Fatos recorrentes, ocorrências e acesso ao vestígio técnico.</span></figcaption></figure>
          <figure><img src="/assets/forensihash-timeline.png" alt="Timeline do ForensiHash mostrando intervalo de validade de certificado e eventos com diferentes estados de timezone" loading="lazy" /><figcaption><strong>Timeline técnica</strong><span>Instantes, intervalos, precisão e domínios temporais preservados.</span></figcaption></figure>
        </div>
      </Section>

      <Section id="timeline" className="arqen-section forensi-dark-section forensi-timeline-section" eyebrow="TIMELINE + PROVENIÊNCIA" title="Organizar o tempo sem reescrever a história.">
        <div className="forensi-two-column"><div><h3>Timeline do Caso</h3><p>Organiza eventos técnicos observados em diferentes fontes do Caso: datas documentais, metadados, assinatura, intervalos de certificado, filesystem e fontes estruturadas quando disponíveis.</p><p>Precisão, timezone, papel temporal e limitações permanecem visíveis. A Timeline não “reconstrói a verdade dos fatos”.</p></div><div><h3>Retorno à origem</h3><p>A proveniência canônica pode registrar arquivo, página, faixa textual, objeto ou stream, campo de metadata/XMP, JSONPath, região OCR, método de parsing e valor bruto, conforme a fonte suportar.</p><p>Campos indisponíveis não são fabricados e duas ocorrências não são fundidas apenas por terem o mesmo valor.</p></div></div>
      </Section>

      <Section id="eficiencia" className="arqen-section forensi-efficiency-section" eyebrow="EFICIÊNCIA ESPERADA" title="Menos operação repetitiva. Mais tempo para revisar.">
        <p className="lead">O ganho esperado está na concentração de tarefas mecânicas e conferências repetíveis. Ainda não existe benchmark público que sustente percentual ou tempo economizado pelo ForensiHash.</p>
        <div className="efficiency-pillar-grid">{efficiencyPillars.map(([title, description]) => <article key={title}><h3>{title}</h3><p>{description}</p></article>)}</div>
        <p className="efficiency-purpose">Tempo eventualmente liberado deve ampliar revisão, interpretação, conferência, análise contextual e redação — não reduzir o julgamento profissional.</p>
      </Section>

      <Section className="arqen-section efficiency-study-section" eyebrow="FUNDAÇÃO PARA ESTUDO" title="Como a Arqen pretende medir o ganho de eficiência.">
        <div className="efficiency-study-layout"><div><p className="lead">O protocolo deverá comparar o mesmo tipo de tarefa e complexidade em dois fluxos equivalentes.</p><div className="efficiency-comparison" role="group" aria-label="Comparação planejada do estudo de eficiência"><span>Fluxo tradicional</span><b aria-hidden="true">×</b><span>Fluxo assistido pelo ForensiHash</span></div><code className="efficiency-formula">redução de tempo = (T_manual − T_FH) / T_manual × 100</code></div><div className="efficiency-metric-list">{efficiencyMetrics.map(metric => <div key={metric.id}><strong>{metric.name}</strong><span>{metric.description}</span></div>)}</div></div>
        <p className="study-status"><strong>Resultados publicados:</strong> {publishedEfficiencyStudies.length}. Nenhum benchmark foi publicado nesta versão.</p>
      </Section>

      <Section id="limitacoes" className="arqen-section forensi-limitations-section" eyebrow="LIMITAÇÕES" title="O que precisa permanecer explícito.">
        <div className="forensi-limitation-grid">{limitations.map((limitation, index) => <article key={limitation.id}><span>{String(index + 1).padStart(2, '0')}</span><p>{limitation.text}</p></article>)}</div>
        <p className="forensi-statement">UNKNOWN não vira MISMATCH. Ausência não vira contradição. Correlação não vira conclusão.</p>
      </Section>

      <Section id="roadmap" className="arqen-section forensi-roadmap-section" eyebrow="EVOLUÇÃO DO FORENSIHASH" title="Disponível, em desenvolvimento e planejado.">
        <p className="lead">O roadmap comunica direção, não prazo. Itens planejados não são apresentados como capacidade atual.</p>
        <div className="forensi-roadmap-columns">{statusOrder.map(status => <section key={status} aria-labelledby={`roadmap-${status.toLowerCase()}`}><h3 id={`roadmap-${status.toLowerCase()}`}>{FEATURE_STATUS_LABELS[status]}</h3>{roadmapItems.filter(item => item.status === status).map(item => <article key={item.id}><strong>{item.name}</strong><p>{item.description}</p></article>)}</section>)}</div>
      </Section>

      <Section className="arqen-section forensi-transparency-section" eyebrow="TRANSPARÊNCIA TÉCNICA" title="Desktop local-first, com dependências e limites visíveis.">
        <div className="forensi-two-column"><div><h3>Processamento principal local</h3><p>Arquivos e Casos permanecem sob controle do usuário no aplicativo desktop e não são enviados automaticamente ao site. A consulta externa de contexto de IP é opcional e configurável.</p></div><div><h3>Produto em desenvolvimento</h3><p>Falha, indisponibilidade, limite excedido, ausência de achados e não aplicabilidade são estados distintos. ExifTool, Tesseract, Poppler e o núcleo Rust condicionam etapas específicas.</p></div></div>
      </Section>

      <Section className="arqen-section forensi-final-cta" eyebrow="FORENSIHASH" title="Conheça um fluxo técnico organizado e revisável.">
        <p className="lead">Capacidade comprovada, limitações explícitas e interpretação preservada nas mãos do profissional.</p>
        <div className="hero-actions"><a className="button-link button-light" href="#funcionalidades">Explorar funcionalidades</a><Link className="text-link text-link--light" to="/customer">Área do Cliente <span aria-hidden="true">↗</span></Link></div>
      </Section>
    </article>
  )
}
