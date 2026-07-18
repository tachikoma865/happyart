/**
 * GLINTRIA - 神秘的な光の粒子演出
 * マウスの動きに合わせて、願いを運ぶ光の粒を生成します
 */

document.addEventListener('mousemove', function (e) {
    // 負荷軽減のため、一定の確率で生成
    if (Math.random() > 0.3) return;

    const sparkle = document.createElement('div');
    sparkle.className = 'sparkle';

    // 生成位置をマウスカーソルの位置に設定
    sparkle.style.left = e.pageX + 'px';
    sparkle.style.top = e.pageY + 'px';

    // ランダムなサイズを設定（少し小さくして上品に）
    const size = Math.random() * 4 + 1;
    sparkle.style.width = size + 'px';
    sparkle.style.height = size + 'px';

    // スピリチュアルな輝きを放つ色（シャンパンゴールド、パールホワイト、淡いローズ）
    const colors = ['#f9e8b3', '#ffffff', '#fff5e6', '#e6f7ff', '#fff0f5'];
    const color = colors[Math.floor(Math.random() * colors.length)];
    sparkle.style.backgroundColor = color;
    sparkle.style.boxShadow = `0 0 ${size * 3}px ${color}`;

    // 放射状ではなく、少し上に昇っていくような動き（上昇気流）
    const destinationX = (Math.random() - 0.5) * 100;
    const destinationY = - (Math.random() * 80 + 20); // 上方向へ

    sparkle.style.setProperty('--x', destinationX + 'px');
    sparkle.style.setProperty('--y', destinationY + 'px');

    document.body.appendChild(sparkle);

    // ゆっくりと消えていく
    const duration = 1500 + Math.random() * 1000;
    sparkle.style.animationDuration = duration + 'ms';

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
