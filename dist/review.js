"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const generative_ai_1 = require("@google/generative-ai");
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
async function reviewCode() {
    // Read the code files
    const indexCode = fs.readFileSync(path.join(__dirname, 'index.ts'), 'utf-8');
    const actionYaml = fs.readFileSync(path.join(__dirname, '..', 'action.yml'), 'utf-8');
    // Initialize Gemini
    const apiKey = process.env.GEMINI_API_KEY || 'test-key';
    const genAI = new generative_ai_1.GoogleGenerativeAI(apiKey);
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
    }
    catch (error) {
        console.error('Error calling Gemini:', error);
    }
}
reviewCode();
