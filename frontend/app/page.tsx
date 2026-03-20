import PushToTalk from '@/components/PushToTalk';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between px-6 py-16">
      {/* Header */}
      <header className="text-center">
        <p className="text-saffron-500 text-sm tracking-widest mb-2">ಅಥ ಶಾಸ್ತ್ರಾರಂಭಃ</p>
        <h1 className="text-4xl font-semibold text-stone-100">ದಶ ಪ್ರಕರಣಗಳು</h1>
        <p className="mt-2 text-stone-400 text-sm max-w-xs mx-auto">
          ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ. ಶಾಸ್ತ್ರಿಗಳು ಪ್ರಾಚೀನ ಗ್ರಂಥಗಳಿಂದ ಉತ್ತರಿಸುವರು.
        </p>
      </header>

      {/* Conversation area */}
      <section className="w-full max-w-xl flex flex-col gap-4 flex-1 justify-center py-12">
        {/* Transcript / response cards will be rendered here */}
        <div className="rounded-2xl border border-stone-800 bg-[#1c1917] p-6 text-center text-stone-500 text-sm">
          ಬಟನ್ ಹಿಡಿದು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ
        </div>
      </section>

      {/* Push-to-talk control */}
      <footer className="flex flex-col items-center gap-4">
        <PushToTalk />
        <p className="text-stone-600 text-xs">Hold to speak · Release to receive</p>
      </footer>
    </main>
  );
}
