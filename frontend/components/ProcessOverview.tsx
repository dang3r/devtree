'use client';

import React from 'react';

export default function ProcessOverview() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="prose prose-invert max-w-none">
        <h1 className="text-3xl font-bold text-white mb-6">
          Understanding the 510(k) Clearance Process
        </h1>

        {/* What is 510(k)? */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-200 mb-4">
            What is the 510(k) Pathway?
          </h2>
          <p className="text-gray-300 mb-4">
            The 510(k) is the most common pathway for medical device approval in the United States.
            Instead of undergoing rigorous new approval processes, companies can prove their device is{' '}
            <strong className="text-green-400">substantially equivalent</strong> to a previously approved device.
          </p>
          <p className="text-gray-300 mb-4">
            By demonstrating substantial equivalence to a <strong className="text-white">predicate device</strong> (an already-cleared device),
            manufacturers reduce the regulatory burden since the FDA is already aware of the device type and its
            safety and effectiveness profile. While devices may still have differences, this approach helps
            decrease the surface area for review.
          </p>
          <div className="bg-green-900/30 border-l-4 border-green-500 p-4 mb-4">
            <p className="text-sm text-green-200">
              <strong>Key Insight:</strong> Each 510(k) device references one or more predicate devices,
              creating a tree-like graph structure that shows how medical devices evolve over time.
            </p>
          </div>
        </section>

        {/* Data Sources */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-200 mb-4">
            Data Sources
          </h2>
          <p className="text-gray-300 mb-4">
            The FDA publishes 510(k) device summaries on their{' '}
            <a
              href="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpub/applica.cfm"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              official website
            </a>
            . These summaries are PDF documents that contain information about the device, its intended use,
            and the predicate devices it references.
          </p>
          <p className="text-gray-300 mb-4">
            The core 510(k) dataset can be downloaded from{' '}
            <a
              href="https://open.fda.gov/data/downloads/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              openFDA
            </a>
            , which provides structured metadata about each device submission.
          </p>
        </section>

        {/* Data Pipeline */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-200 mb-4">
            Data Extraction Pipeline
          </h2>
          <p className="text-gray-300 mb-4">
            DevTree uses a multi-stage pipeline to extract and visualize predicate relationships:
          </p>

          <div className="space-y-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-200 mb-2">
                1. Download PDF Summaries
              </h3>
              <p className="text-gray-400 text-sm">
                For each 510(k) device in the openFDA dataset, download the corresponding PDF summary
                from the FDA website. The system tracks which PDFs have been downloaded and respects
                FDA rate limits.
              </p>
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-200 mb-2">
                2. Extract Text from PDFs
              </h3>
              <p className="text-gray-400 text-sm">
                Extract text content from PDFs using embedded text when available, or OCR for scanned documents.
                This step handles both machine-readable PDFs and image-based PDFs that require optical character recognition.
              </p>
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-200 mb-2">
                3. Extract Predicate Relationships
              </h3>
              <p className="text-gray-400 text-sm mb-2">
                Identify predicate device IDs (e.g., "K123456") from the extracted text using a multi-method approach:
              </p>
              <ul className="list-disc list-inside text-sm text-gray-400 space-y-1 ml-4">
                <li><strong className="text-gray-300">Regex matching:</strong> Fast pattern matching for standard K-number formats</li>
                <li><strong className="text-gray-300">AI extraction:</strong> Claude Code processes PDFs (including images) to find predicates missed by regex</li>
                <li><strong className="text-gray-300">Human overrides:</strong> Manual corrections for edge cases and errors</li>
              </ul>
              <p className="text-gray-400 text-sm mt-2">
                The results are merged with a priority system: Human &gt; AI &gt; Regex.
              </p>
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-200 mb-2">
                4. Build the Graph
              </h3>
              <p className="text-gray-400 text-sm">
                Combine all extracted predicate relationships into a directed graph structure. Each device
                becomes a node, and each predicate relationship becomes an edge pointing from the new device
                to its predicate.
              </p>
            </div>
          </div>
        </section>

        {/* Extraction Challenges */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-200 mb-4">
            Extraction Challenges
          </h2>
          <p className="text-gray-300 mb-4">
            Extracting predicate relationships is not as simple as regex matching. The PDF summaries
            vary widely in quality and format:
          </p>
          <ul className="list-disc list-inside text-gray-400 space-y-2 ml-4">
            <li>Some summaries are scanned documents without embedded text</li>
            <li>Some have malformed K-numbers (e.g., "K1 00218", "ki00218", "K10O218")</li>
            <li>Some reference many devices but only a subset are actual predicates</li>
            <li>Some have predicate IDs embedded in images or tables</li>
            <li>Some don't mention predicates at all in the summary text</li>
          </ul>
          <p className="text-gray-300 mt-4">
            The multi-method approach (regex + AI + manual overrides) helps overcome these challenges
            and provides the most complete dataset possible.
          </p>
        </section>

        {/* Graph Structure */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-200 mb-4">
            Understanding the Graph
          </h2>
          <p className="text-gray-300 mb-4">
            The DevTree graph visualizes the evolutionary relationships between medical devices:
          </p>
          <ul className="list-disc list-inside text-gray-400 space-y-2 ml-4">
            <li>
              <strong className="text-gray-300">Nodes:</strong> Each node represents a 510(k) device, color-coded by risk class:
              <ul className="list-circle list-inside ml-6 mt-1 space-y-1">
                <li><span className="text-red-500 font-semibold">Red</span> = Class III (High Risk)</li>
                <li><span className="text-amber-500 font-semibold">Amber</span> = Class II (Moderate Risk)</li>
                <li><span className="text-green-500 font-semibold">Green</span> = Class I (Low Risk)</li>
              </ul>
            </li>
            <li>
              <strong className="text-gray-300">Edges:</strong> Arrows point from a new device to its predicate(s), showing the
              "is substantially equivalent to" relationship
            </li>
            <li>
              <strong className="text-gray-300">Layouts:</strong> View as a hierarchical graph (tree-like) or timeline (chronological by decision date)
            </li>
          </ul>
        </section>

        {/* Technical Stack */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-200 mb-4">
            Technical Implementation
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-200 mb-2">Backend</h3>
              <ul className="list-disc list-inside text-sm text-gray-400 space-y-1">
                <li>Python 3.14 with type hints</li>
                <li>uv package manager</li>
                <li>PyMuPDF for PDF processing</li>
                <li>Pydantic for data validation</li>
                <li>Regex + AI for extraction</li>
              </ul>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-200 mb-2">Frontend</h3>
              <ul className="list-disc list-inside text-sm text-gray-400 space-y-1">
                <li>Next.js (static export)</li>
                <li>Cytoscape.js for visualization</li>
                <li>Tailwind CSS for styling</li>
                <li>Client-side graph rendering</li>
                <li>GitHub Pages hosting</li>
              </ul>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
