import { GoogleGenerativeAI } from '@google/generative-ai';
import * as fs from 'fs';
import * as path from 'path';

async function reviewCode() {
  // Read the code files
  const indexCode = fs.readFileSync(path.join(__dirname, 'index.ts'), 'utf-8');
  const actionYaml = fs.readFileSync(path.join(__dirname, '..', 'action.yml'), 'utf-8');

  // Initialize Gemini
  const apiKey = process.env.GEMINI_API_KEY || 'test-key';
  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: 'gemini-1.5-pro' });

  const prompt = `Gemini, you are the Lead Architect. Review this GitHub Action code for Delimit. 

Look specifically for:
1) CI/CD security risks (e.g., leaking the DELIMIT_API_KEY in action logs)
2) Edge cases in file path resolution for the openapi spec
3) Best practices for Node20 actions

action.yml:
\`\`\`yaml
${actionYaml}
\`\`\`

src/index.ts:
\`\`\`typescript
${indexCode}
\`\`\`

Suggest specific code improvements with examples.`;

  try {
    const result = await model.generateContent(prompt);
    const response = await result.response;
    console.log('=== GEMINI ARCHITECTURAL REVIEW ===\n');
    console.log(response.text());
  } catch (error) {
    console.error('Error calling Gemini:', error);
  }
}

reviewCode();