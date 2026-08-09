import { Section } from '../components/ui'

export function DdnaPage() {
  return (
    <>
      <Section eyebrow="DDNA · DOCUMENT DNA" title="IDENTIDADE TÉCNICA VERIFICÁVEL PARA EVIDÊNCIAS DIGITAIS.">
        <span className="development-flag">EM DESENVOLVIMENTO</span>
        <p className="lead">Uma tecnologia em desenvolvimento no ecossistema ForensiHash para associar a uma evidência digital um registro técnico verificável de identidade, integridade e contexto.</p>
      </Section>
      <Section className="surface-section" eyebrow="VISÃO CONCEITUAL" title="DO ARQUIVO À VERIFICAÇÃO">
        <div className="process-flow" aria-label="Fluxo conceitual do DDNA">
          {['ARQUIVO', 'IDENTIDADE CRIPTOGRÁFICA', 'REGISTRO TÉCNICO', 'DDNA', 'VERIFICAÇÃO'].map((item, index) => <div key={item}><span>{item}</span>{index < 4 && <b aria-hidden="true">↓</b>}</div>)}
        </div>
        <p className="institutional-note">Este fluxo representa uma proposta arquitetural. Nenhum registro DDNA, assinatura CAdES, timestamp ou verificação DDNA foi implementado.</p>
      </Section>
      <Section eyebrow="CADEIA DE CUSTÓDIA" title="ELEMENTOS PARA APOIAR RASTREABILIDADE.">
        <p className="lead">O DDNA é projetado para apoiar a construção e verificação de registros de cadeia de custódia digital. A visão futura pode envolver hash da evidência, eventos, assinatura digital, timestamp e verificação independente. Esses recursos permanecem planejados.</p>
      </Section>
      <Section className="surface-section" eyebrow="INSTITUIÇÕES" title="DOCUMENTO GERADO. REFERÊNCIA PRESERVADA.">
        <div className="horizontal-flow">{['DOCUMENTO GERADO', 'REGISTRO', 'ARQUIVAMENTO', 'VERIFICAÇÃO FUTURA'].map((item) => <span key={item}>{item}</span>)}</div>
        <p>A proposta considera organizações que produzem ou recebem documentos digitais, incluindo instituições financeiras, seguradoras, escritórios, departamentos jurídicos, auditoria e compliance. Não há afirmação de adoção institucional.</p>
      </Section>
    </>
  )
}
