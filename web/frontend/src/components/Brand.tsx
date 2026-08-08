import { Link } from "react-router-dom";

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="ForensiHash - voltar para a página inicial">
      <img
        src="/assets/forensihash_logo_completo.png"
        alt="ForensiHash"
        className="brand__logo"
      />
    </Link>
  );
}