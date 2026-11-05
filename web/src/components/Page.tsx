import type { ReactNode } from "react";
import Backdrop from "./Backdrop";
import Header from "./Header";

export default function Page({ children, narrow = true }: { children: ReactNode; narrow?: boolean }) {
  return (
    <div className="stage">
      <Backdrop />
      <Header />
      <main className={narrow ? "page-wrap" : undefined}>{children}</main>
    </div>
  );
}
