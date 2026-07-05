const useLegacyClipboardCopy = (text: string): void => {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.setAttribute('readonly', '');
  textArea.style.cssText = [
    'border:0',
    'height:1px',
    'left:-9999px',
    'opacity:0',
    'padding:0',
    'position:fixed',
    'top:0',
    'width:1px',
  ].join(';');

  document.body.appendChild(textArea);
  textArea.select();

  try {
    if (!document.execCommand('copy')) {
      throw new Error('Legacy clipboard command returned false');
    }
  } finally {
    textArea.remove();
  }
};

export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (error) {
      console.warn('Navigator clipboard API failed, falling back to textarea copy:', error);
    }
  }

  useLegacyClipboardCopy(text);
}
