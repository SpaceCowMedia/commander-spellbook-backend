// Drives the admin in a real Chromium-family browser: one command per line on stdin.
//
//   login [user] [password]     log in at /admin/login/ (default agent / agent-password)
//   nav <path>                  open a path of the server (or a full URL)
//   wait <selector>             wait for an element to be visible
//   click <selector>            click an element
//   submit <selector>           click an element and wait for the page it loads
//   fill <selector> <text>      replace the value of a field (\n for new lines)
//   hover <selector>            move the mouse over an element
//   scroll <selector>           bring an element to the top of the viewport
//   shot <name> [selector]      screenshot the page, or one element, into screenshots/<name>.png
//   text <selector>             print the text of an element
//   eval <expression>           print what an expression evaluates to in the page
//   scheme light|dark           switch the color scheme the page sees
//   errors                      print the console errors seen so far
//
// Lines starting with # are comments. Selectors are Playwright's, so `text=Save` works too.
// RUN_BACKEND_URL is the server (http://127.0.0.1:8765), BROWSER_PATH the browser when not found.
import { createRequire } from 'module';
import { existsSync, mkdirSync, readdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import readline from 'readline';

const here = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = createRequire(path.join(here, 'package.json'))('playwright-core');
const base = process.env.RUN_BACKEND_URL ?? 'http://127.0.0.1:8765';
const screenshots = path.join(here, 'screenshots');

function browserPath() {
    if (process.env.BROWSER_PATH) {
        return process.env.BROWSER_PATH;
    }
    const candidates = [];
    // Edge's own folder may be missing while its EdgeCore runtime is there, one folder per version
    const core = 'C:/Program Files (x86)/Microsoft/EdgeCore';
    if (existsSync(core)) {
        const versions = readdirSync(core).filter(name => /^\d/.test(name)).sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
        candidates.push(...versions.map(version => `${core}/${version}/msedge.exe`));
    }
    candidates.push(
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    );
    const found = candidates.find(candidate => existsSync(candidate));
    if (!found) {
        throw new Error('No Chromium-family browser found: set BROWSER_PATH');
    }
    return found;
}

function argument(line) {
    const space = line.indexOf(' ');
    return space < 0 ? [line, ''] : [line.slice(0, space), line.slice(space + 1)];
}

function selectorAndText(rest) {
    // the selector ends at the first space outside quotes and brackets
    let depth = 0;
    let quote = null;
    for (let index = 0; index < rest.length; index++) {
        const character = rest[index];
        if (quote) {
            if (character === quote) quote = null;
        } else if (character === '"' || character === "'") {
            quote = character;
        } else if ('[('.includes(character)) {
            depth++;
        } else if ('])'.includes(character)) {
            depth--;
        } else if (character === ' ' && depth === 0) {
            return [rest.slice(0, index), rest.slice(index + 1).replaceAll('\\n', '\n')];
        }
    }
    return [rest, ''];
}

const executablePath = browserPath();
const browser = await chromium.launch({ executablePath, headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(`pageerror: ${error.message}`));
page.on('console', message => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
console.log(`browser: ${executablePath}`);

const lines = readline.createInterface({ input: process.stdin });
let failed = false;
for await (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) {
        continue;
    }
    const [command, rest] = argument(line);
    try {
        switch (command) {
            case 'login': {
                const [user = 'agent', password = 'agent-password'] = rest.split(' ').filter(Boolean);
                await page.goto(`${base}/admin/login/`);
                await page.fill('#id_username', user);
                await page.fill('#id_password', password);
                await Promise.all([page.waitForNavigation(), page.click('input[type=submit]')]);
                if (page.url().includes('/login/')) throw new Error('login refused');
                break;
            }
            case 'nav':
                await page.goto(rest.startsWith('http') ? rest : `${base}${rest}`);
                break;
            case 'wait':
                await page.locator(rest).first().waitFor();
                break;
            case 'click':
                await page.locator(rest).first().click();
                break;
            case 'submit':
                await Promise.all([page.waitForNavigation(), page.locator(rest).first().click()]);
                break;
            case 'fill': {
                const [selector, text] = selectorAndText(rest);
                await page.locator(selector).first().fill(text);
                break;
            }
            case 'hover':
                await page.locator(rest).first().hover();
                break;
            case 'scroll':
                await page.locator(rest).first().evaluate(node => { node.scrollIntoView(); window.scrollBy(0, -80); });
                break;
            case 'shot': {
                const [name, selector] = selectorAndText(rest);
                mkdirSync(screenshots, { recursive: true });
                const file = path.join(screenshots, `${name}.png`);
                await (selector ? page.locator(selector).first() : page).screenshot({ path: file });
                console.log(`shot: ${file}`);
                break;
            }
            case 'text':
                console.log(`text: ${(await page.locator(rest).first().innerText()).trim()}`);
                break;
            case 'eval':
                console.log(`eval: ${JSON.stringify(await page.evaluate(rest))}`);
                break;
            case 'scheme':
                await page.emulateMedia({ colorScheme: rest });
                break;
            case 'errors':
                console.log(errors.length ? errors.join('\n') : 'errors: none');
                break;
            default:
                throw new Error(`unknown command ${command}`);
        }
    } catch (error) {
        failed = true;
        console.log(`failed: ${line}\n  ${error.message.split('\n')[0]}`);
        break;
    }
}
await browser.close();
process.exit(failed ? 1 : 0);
