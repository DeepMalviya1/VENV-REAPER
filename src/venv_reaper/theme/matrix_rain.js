(function() {
  const doc = window.parent.document;
  if (doc.getElementById('matrix-canvas')) return;
  const canvas = doc.createElement('canvas');
  canvas.id = 'matrix-canvas';
  Object.assign(canvas.style, {
    position:'fixed', top:'0', left:'0', width:'100vw', height:'100vh',
    zIndex:'-1', opacity:'0.16', pointerEvents:'none',
  });
  doc.body.prepend(canvas);
  const ctx = canvas.getContext('2d');
  const CHARS = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEF<>{}[]|/\\';
  const FS = 14; let cols, drops;
  function resize() {
    canvas.width = window.parent.innerWidth;
    canvas.height = window.parent.innerHeight;
    cols = Math.floor(canvas.width / FS);
    drops = Array(cols).fill(1);
  }
  resize();
  window.parent.addEventListener('resize', resize);
  function draw() {
    ctx.fillStyle = 'rgba(0,0,0,0.05)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = FS + 'px monospace';
    for (let i = 0; i < drops.length; i++) {
      const bright = Math.random() > 0.95;
      ctx.fillStyle = bright ? '#ffffff' : (Math.random() > 0.7 ? '#00ff41' : '#005c18');
      ctx.fillText(CHARS[Math.floor(Math.random() * CHARS.length)], i * FS, drops[i] * FS);
      if (drops[i] * FS > canvas.height && Math.random() > 0.975) drops[i] = 0;
      drops[i]++;
    }
  }
  setInterval(draw, 45);
})();
