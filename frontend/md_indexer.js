import fs from 'fs';
import path from 'path';



function removeScriptTags(text) {
    const scriptRegex = /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi;
    const styleRegex = /<style\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/style>/gi;
    return text.replace(scriptRegex, '').replace(styleRegex, '');
}

function getMarkdownFiles(dir) {
    let markdownFiles = [];
    const files = fs.readdirSync(dir);

    for (const file of files) {
        const filePath = path.join(dir, file);
        const stats = fs.statSync(filePath);

        if (stats.isDirectory()) {
            markdownFiles = markdownFiles.concat(getMarkdownFiles(filePath));
        } else if (path.extname(file) === '.md') {
            const content = fs.readFileSync(filePath, 'utf-8');
            markdownFiles.push({
                path: filePath.replace("src/routes/docs",""),
                content: removeScriptTags(content),
                filename: file,
            });
        }
    }

    return markdownFiles;
}

console.log("indexing markdown files...");

const markdownFiles = getMarkdownFiles('./src/routes/docs');

fs.writeFileSync('./src/md_indexer.json', JSON.stringify(markdownFiles, null, 2));

console.log(`done indexing markdown ${markdownFiles.length} files`);
