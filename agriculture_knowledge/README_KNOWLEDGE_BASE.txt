# How to Add Verified Agriculture Documents to the Knowledge Base

Welcome to the Knowledge Base management directory for the Smart Agriculture AI Chatbot.

## Supported Document Formats
1. **Plain Text (`.txt`)**
2. **Markdown (`.md`)**
3. **Adobe PDF (`.pdf`)**

## Guidelines for Adding Documents
To maintain 100% integrity and prevent hallucinated agricultural advice:
1. **Use Authoritative Sources Only:**
   - ICAR (Indian Council of Agricultural Research) - https://icar.org.in
   - TNAU Agritech Portal - https://agritech.tnau.ac.in
   - State Agricultural Universities (SAUs) & Krishi Vigyan Kendras (KVKs)
   - Ministry of Agriculture & Farmers Welfare - https://agricoop.nic.in
2. **Include Clear Metadata Headers:**
   For text/markdown files, please include at the top:
   - Source: [Name of official institution]
   - Document Title: [Official document title]
   - Reference URL: [Link to official publication or circular]
   - Publication Year: [Year]
3. **Multilingual Content:**
   Documents can be placed in English, Tamil, Hindi, Telugu, Kannada, or Malayalam. The retrieval engine parses Unicode scripts directly.
4. **Re-indexing:**
   Whenever you add or delete files in this folder, re-indexing happens automatically or can be refreshed via the system API `/api/chatbot/reload_knowledge`.
