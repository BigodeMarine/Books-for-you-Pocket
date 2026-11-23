
import type { Metadata } from "next";

// Metadados padrão utilizados pela aplicação.
export const metadata: Metadata = {
  title: "Books for Your Pocket",
  description:
    "Descubra livros, quadrinhos e mangás. Explore edições e encontre ofertas para sua próxima leitura.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
