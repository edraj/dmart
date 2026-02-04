<script lang="ts">
    import {createEventDispatcher, onMount} from "svelte";
    import {Editor, format, h} from 'typewriter-editor';
    import {Card} from "flowbite-svelte";

    const dispatch = createEventDispatcher();

    let {
        uid = "",
        content = $bindable(""),
    } : {
        uid?: string,
        content: string
    } = $props();

    let maindiv;
    let editor = null;

    const underline = format({
        name: 'underline',
        selector: 'u',
        styleSelector: '[style*="text-decoration:underline"], [style*="text-decoration: underline"]',
        commands: editor => () => editor.toggleTextFormat({ underline: true }),
        shortcuts: 'Mod+U',
        render: (attributes, children) => h('u', null, children),
    });

    const strike = format({
        name: 'strike',
        selector: 'strike, s',
        styleSelector: '[style*="text-decoration:line-through"], [style*="text-decoration: line-through"]',
        commands: editor => () => editor.toggleTextFormat({ strike: true }),
        shortcuts: 'Mod+Shift+X',
        render: (attributes, children) => h('s', null, children),
    });

    const superscript = format({
        name: 'superscript',
        selector: 'sup',
        commands: editor => () => editor.toggleTextFormat({ superscript: true }),
        render: (attributes, children) => h('sup', null, children),
    });

    const subscript = format({
        name: 'subscript',
        selector: 'sub',
        commands: editor => () => editor.toggleTextFormat({ subscript: true }),
        render: (attributes, children) => h('sub', null, children),
    });

    const alignLeft = format({
        name: 'align-left',
        selector: '[style*="text-align:left"], [style*="text-align: left"]',
        commands: editor => () => editor.formatLine({ align: 'left' }),
        render: (attributes, children) => h('div', { style: 'text-align: left' }, children),
    });

    const alignCenter = format({
        name: 'align-center',
        selector: '[style*="text-align:center"], [style*="text-align: center"]',
        commands: editor => () => editor.formatLine({ align: 'center' }),
        render: (attributes, children) => h('div', { style: 'text-align: center' }, children),
    });

    const alignRight = format({
        name: 'align-right',
        selector: '[style*="text-align:right"], [style*="text-align: right"]',
        commands: editor => () => editor.formatLine({ align: 'right' }),
        render: (attributes, children) => h('div', { style: 'text-align: right' }, children),
    });

    const alignJustify = format({
        name: 'align-justify',
        selector: '[style*="text-align:justify"], [style*="text-align: justify"]',
        commands: editor => () => editor.formatLine({ align: 'justify' }),
        render: (attributes, children) => h('div', { style: 'text-align: justify' }, children),
    });

    onMount(async () => {
        editor = new Editor({
            root: maindiv,
            html: content,
            types: {
                // Line formats
                lines: [
                    'paragraph', 
                    'header', 
                    'list', 
                    'blockquote', 
                    'code-block', 
                    'hr',
                    alignLeft,
                    alignCenter,
                    alignRight,
                    alignJustify
                ],
                // Text formats
                formats: [
                    'bold', 
                    'italic', 
                    underline, 
                    strike, 
                    superscript, 
                    subscript, 
                    'code', 
                    'link',
                    'clear'
                ],
                embeds: [
                    'image', 
                    'br'
                ]
            }
        });

        editor.on('change', () => {
            content = editor.getHTML();
            dispatch("changed");
        });

        setupToolbar();
    });

    function setupToolbar() {
            const toolbar = document.createElement('div');
            toolbar.id = `toolbar-${uid}`;
            toolbar.className = 'editor-toolbar';

            const textFormatGroup = document.createElement('div');
            textFormatGroup.className = 'toolbar-group';
            
            const lineFormatGroup = document.createElement('div');
            lineFormatGroup.className = 'toolbar-group';
            
            const alignmentGroup = document.createElement('div');
            alignmentGroup.className = 'toolbar-group';
            
            const insertGroup = document.createElement('div');
            insertGroup.className = 'toolbar-group';
            
            const historyGroup = document.createElement('div');
            historyGroup.className = 'toolbar-group';
            
            const directionGroup = document.createElement('div');
            directionGroup.className = 'toolbar-group';

            addToolbarButton(textFormatGroup, 'Bold', 'B', () => editor.formatText('bold'));
            addToolbarButton(textFormatGroup, 'Italic', 'I', () => editor.formatText('italic'));
            addToolbarButton(textFormatGroup, 'Underline', 'U', () => editor.formatText('underline'));
            addToolbarButton(textFormatGroup, 'Strike', 'S', () => editor.formatText('strike'));
            addToolbarButton(textFormatGroup, 'Superscript', 'x²', () => editor.formatText('superscript'));
            addToolbarButton(textFormatGroup, 'Subscript', 'x₂', () => editor.formatText('subscript'));
            addToolbarButton(textFormatGroup, 'Remove Format', 'X', () => editor.removeFormat());

            addToolbarButton(lineFormatGroup, 'Heading 1', 'H1', () => editor.formatLine({ header: 1 }));
            addToolbarButton(lineFormatGroup, 'Heading 2', 'H2', () => editor.formatLine({ header: 2 }));
            addToolbarButton(lineFormatGroup, 'Paragraph', '¶', () => editor.formatLine('paragraph'));
            addToolbarButton(lineFormatGroup, 'Blockquote', '""', () => editor.formatLine('blockquote'));
            addToolbarButton(lineFormatGroup, 'Ordered List', '1.', () => editor.formatLine({ list: 'ordered' }));
            addToolbarButton(lineFormatGroup, 'Unordered List', '•', () => editor.formatLine({ list: 'bullet' }));
            addToolbarButton(lineFormatGroup, 'Horizontal Rule', '—', () => editor.formatLine('hr'));

            addToolbarButton(alignmentGroup, 'Align Left', '↤', () => editor.formatLine('align-left'));
            addToolbarButton(alignmentGroup, 'Align Center', '↔', () => editor.formatLine('align-center'));
            addToolbarButton(alignmentGroup, 'Align Right', '↦', () => editor.formatLine('align-right'));
            addToolbarButton(alignmentGroup, 'Justify', '☰', () => editor.formatLine('align-justify'));

            addToolbarButton(insertGroup, 'Link', '🔗', () => {
                const url = prompt('Enter URL:');
                if (url) editor.formatText({ link: url });
            });

            addToolbarButton(insertGroup, 'Image', '🖼', () => {
                const url = prompt('Enter image URL:');
                if (url) editor.insert({ image: url });
            });

            addToolbarButton(historyGroup, 'Undo', '↶', () => editor.modules.history.undo());
            addToolbarButton(historyGroup, 'Redo', '↷', () => editor.modules.history.redo());




            addToolbarButton(directionGroup, 'LTR', 'LTR', () => {
                maindiv.dir = 'ltr';
                editor.formatLine({ direction: 'ltr' });
            });
            addToolbarButton(directionGroup, 'RTL', 'RTL', () => {
                maindiv.dir = 'rtl';
                editor.formatLine({ direction: 'rtl' });
            });

            toolbar.appendChild(textFormatGroup);
            toolbar.appendChild(lineFormatGroup);
            toolbar.appendChild(alignmentGroup);
            toolbar.appendChild(insertGroup);
            toolbar.appendChild(historyGroup);
            toolbar.appendChild(directionGroup);

            maindiv.parentNode.insertBefore(toolbar, maindiv);
    }

    function addToolbarButton(toolbar, title, icon, action) {
        const button = document.createElement('button');
        button.title = title;
        button.className = 'toolbar-button';
        button.textContent = icon;

        button.addEventListener('click', action);
        toolbar.appendChild(button);
    }

    $effect(() => {
        if (editor && typeof editor.setHTML === 'function') {
            const currentHtml = editor.getHTML();
            if (content !== currentHtml) {
                editor.setHTML(content);
            }
        }
    });
</script>

<Card class="h-full max-w-full pt-1">
    <article class="prose max-w-full">
        <div class="pt-1 editor-container" bind:this="{maindiv}" id="htmleditor-{uid}"></div>
    </article>
</Card>

<style>
    .editor-container {
        font-family: "uthmantn";
        font-size: 1rem !important;
        min-height: 200px;
        border: 1px solid #e2e8f0;
        border-radius: 0.25rem;
        padding: 1rem;
    }

    :global(.editor-toolbar) {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        padding: 0.5rem;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 0.25rem;
        margin-bottom: 0.5rem;
    }

    :global(.toolbar-group) {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        padding: 0.25rem;
        border: 1px solid #e2e8f0;
        border-radius: 0.25rem;
        background-color: #ffffff;
    }

    :global(.toolbar-button) {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.25rem;
        width: 2rem;
        height: 2rem;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 0.25rem;
        cursor: pointer;
        font-size: 0.75rem;
    }

    :global(.toolbar-button svg) {
        width: 1rem;
        height: 1rem;
    }

    :global(.toolbar-button:hover) {
        background-color: #f1f5f9;
    }

    :global(.toolbar-button:active) {
        background-color: #e2e8f0;
    }
    
    :global(.toolbar-button.active) {
        background-color: #e2e8f0;
        border-color: #cbd5e1;
    }

    :global([dir="rtl"]) {
        text-align: right;
    }

    /* Ensure editor content is properly styled */
    :global(.editor-container h1) {
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }

    :global(.editor-container h2) {
        font-size: 1.25rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }

    :global(.editor-container blockquote) {
        border-left: 3px solid #e2e8f0;
        padding-left: 1rem;
        margin-left: 0;
        font-style: italic;
    }

    :global([dir="rtl"] .editor-container blockquote) {
        border-left: none;
        border-right: 3px solid #e2e8f0;
        padding-left: 0;
        padding-right: 1rem;
        margin-right: 0;
    }
</style>
