'use client';

export default function Contact() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="prose prose-invert max-w-none">
        <h1 className="text-3xl font-bold text-white mb-6">
          Contact
        </h1>

        <section className="mb-8">
          <p className="text-gray-300 mb-4">
            Made by Daniel Cardoza! You can find me on the internet at{' '}
            <a
              href="https://www.linkedin.com/in/dcardoza/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              LinkedIn
            </a>
            {' '}and{' '}
            <a
              href="https://danielcardoza.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              danielcardoza.com
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
