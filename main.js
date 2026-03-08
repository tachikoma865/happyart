/**
 * LUMINA ART - 神秘的なキラキラ演出
 * マウスの動きに合わせて光の粒を生成します
 */

document.addEventListener('mousemove', function (e) {
    const sparkle = document.createElement('div');
    sparkle.className = 'sparkle';

    // 生成位置をマウスカーソルの位置に設定
    sparkle.style.left = e.pageX + 'px';
    sparkle.style.top = e.pageY + 'px';

    // ランダムなサイズを設定
    const size = Math.random() * 5 + 2;
    sparkle.style.width = size + 'px';
    sparkle.style.height = size + 'px';

    // ランダムな色（ゴールド、シルバー、ホワイト）を設定
    const colors = ['#D4AF37', '#C0C0C0', '#FFFFFF', '#FFF8DC', '#FFD700'];
    const color = colors[Math.floor(Math.random() * colors.length)];
    sparkle.style.backgroundColor = color;
    sparkle.style.boxShadow = `0 0 ${size * 2}px ${color}`;

    // 移動方向をランダムに設定
    const destinationX = (Math.random() - 0.5) * 120;
    const destinationY = (Math.random() - 0.5) * 120;

    sparkle.style.setProperty('--x', destinationX + 'px');
    sparkle.style.setProperty('--y', destinationY + 'px');

    document.body.appendChild(sparkle);

    // アニメーション終了後に要素を削除
    const duration = 600 + Math.random() * 600;
    setTimeout(() => {
        sparkle.remove();
    }, duration);
});

// タッチデバイス（スマホ）向け：スクロール時やタップ時にも少し粒を出す
document.addEventListener('touchmove', function (e) {
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousemove', {
        clientX: touch.clientX,
        clientY: touch.clientY,
        pageX: touch.pageX,
        pageY: touch.pageY
    });
    document.dispatchEvent(mouseEvent);
}, { passive: true });
