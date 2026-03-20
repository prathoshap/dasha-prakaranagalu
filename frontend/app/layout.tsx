import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ದಶ ಪ್ರಕರಣಗಳು',
  description: 'ಮಾಧ್ವ ತತ್ವಜ್ಞಾನದ ಸಂವಾದ ಕೇಂದ್ರ',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="kn">
      <body className="min-h-screen bg-[#0c0a09] text-stone-100 antialiased">
        {children}
      </body>
    </html>
  );
}
