import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Veracust | Synthetic Audio Forensics",
  description: "AI voice-clone and synthetic-audio forensic analysis",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
