import { Link } from 'react-router-dom'
import { ReferenceLink } from '../components/ReferenceLink'
import { Section, TechnicalValue } from '../components/ui'
import { affectedContexts, analysisLayers } from '../content/institutional'

export function HomePage() {
  return (
    <>
      <Section className="hero">
        <div className="hero-grid">
          <div>
            <p className="eyebrow">ENGENHARIA FORENSE DIGITAL</p>
            <h1>ANÁLISE E RASTREABILIDADE<br />DE EVIDÊNCIAS DIGITAIS.</h1>
            <p className="hero-copy">O ForensiHash centraliza verificações técnicas de documentos e arquivos digitais, permitindo examinar integridade, metadados, estrutura, assinaturas e outros vestígios em um único ambiente.</p>
            <div className="hero-actions">
              <Link className="button-link" to="/app/analysis">Iniciar análise</Link>
              <Link className="text-link" to="/ddna">Conhecer o DDNA →</Link>
            </div>
          </div>
          <div className="technical-demo" aria-label="Demonstração fictícia de saída técnica">
            <span className="demo-label">DEMO · DADOS FICTÍCIOS</span>
            <dl>
              <div><dt>FILE</dt><dd>document-demo.pdf</dd></div>
              <div><dt>TYPE</dt><dd>PDF / 1.7</dd></div>
              <div><dt>SHA-256</dt><dd><TechnicalValue>8F21A0C4…D71E</TechnicalValue></dd></div>
              <div><dt>SIGNATURE</dt><dd>DETECTED</dd></div>
              <div><dt>STATUS</dt><dd>ANALYZED</dd></div>
            </dl>
          </div>
        </div>
      </Section>

      <Section eyebrow="CONTEXTO" title="DOCUMENTOS DIGITAIS MOVIMENTAM RELAÇÕES REAIS." className="surface-section">
        <p className="lead">Documentos eletrônicos participam de contratos, operações financeiras, seguros, telecomunicações, relações jurídicas, processos administrativos e rotinas corporativas. Quando um arquivo é contestado, integridade, origem técnica e rastreabilidade precisam ser examinadas sem presumir fraude.</p>
        <div className="border-grid three-columns">
          {affectedContexts.map(([title, description]) => <article key={title}><h3>{title}</h3><p>{description}</p></article>)}
        </div>
      </Section>

      <Section eyebrow="FORENSIHASH" title="UMA EVIDÊNCIA. MÚLTIPLAS CAMADAS DE ANÁLISE.">
        <div className="border-grid three-columns analysis-grid">
          {analysisLayers.map(([number, title, description]) => (
            <article key={number}><span className="item-number">{number}</span><h3>{title}</h3><p>{description}</p></article>
          ))}
        </div>
        <p className="institutional-note">O ForensiHash é uma ferramenta de apoio à análise técnica. Os resultados devem ser interpretados em conjunto com os demais elementos disponíveis no caso analisado.</p>
      </Section>

      <Section eyebrow="ASSINATURAS ELETRÔNICAS" title="CONTEXTO TÉCNICO, SEM CONCLUSÕES AUTOMÁTICAS." className="surface-section">
        <div className="split-copy">
          <div><p>A legislação brasileira diferencia modalidades de assinatura eletrônica e estabelece contextos próprios de utilização. A análise técnica de um arquivo não substitui essa avaliação jurídica nem presume validade ou invalidade.</p><ReferenceLink id="lei-14063" /></div>
          <div><p>A ICP-Brasil é descrita pelo ITI como uma cadeia hierárquica de confiança para emissão de certificados digitais. O ForensiHash não é autoridade certificadora e não afirma homologação institucional.</p><ReferenceLink id="iti-icp-brasil" /></div>
        </div>
      </Section>

      <Section eyebrow="ECOSSISTEMA" title="ANÁLISE HOJE. RASTREABILIDADE EM DESENVOLVIMENTO.">
        <div className="product-comparison">
          <article><span>FORENSIHASH</span><h3>Plataforma de análise técnica</h3><p>Examina uma evidência e organiza fatos, estruturas, estados, limitações e findings.</p><Link to="/forensihash">Conhecer a plataforma →</Link></article>
          <article><span>DDNA · EM DESENVOLVIMENTO</span><h3>Identidade e registro técnico</h3><p>Proposta para apoiar identidade, integridade, rastreabilidade e custódia verificável.</p><Link to="/ddna">Conhecer a visão →</Link></article>
        </div>
      </Section>
    </>
  )
}
