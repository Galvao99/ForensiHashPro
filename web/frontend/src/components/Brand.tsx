import { Link } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";

const LIGHT_LOGO = "/assets/forensihash_logo_completo.png";
const DARK_LOGO = "/assets/ChatGPT Image 8 de ago. de 2026, 19_11_22.png";

export function Brand() {
  const { resolvedTheme } = useTheme();
  return (
    <Link to="/" className="brand" aria-label="ForensiHash - voltar para a página inicial">
      <img
        src={resolvedTheme === "DARK" ? DARK_LOGO : LIGHT_LOGO}
        alt="ForensiHash"
        className="brand__logo"
      />
    </Link>
  );
}
