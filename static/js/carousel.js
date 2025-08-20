// Carrousel coverflow interactif pour la landing page
window.addEventListener('DOMContentLoaded', function() {
  const coverflow = document.querySelector('.carousel-coverflow');
  const leftBtn = document.querySelector('.carousel-arrow.left');
  const rightBtn = document.querySelector('.carousel-arrow.right');
  const container = document.querySelector('.carousel-container');
  let current = 0;

  function renderCoverflow(idx) {
    coverflow.innerHTML = '';
    // Sur mobile, 3 cartes visibles, toutes avec titre/image/desc
    if (window.innerWidth <= 900) {
      [-1, 0, 1].forEach((offset) => {
        const pos = (idx + offset + carouselData.length) % carouselData.length;
        const data = carouselData[pos];
        let className = 'carousel-item';
        if (offset === 0) className += ' center';
        else if (offset === -1) className += ' left';
        else if (offset === 1) className += ' right';
        coverflow.innerHTML += `
          <div class="${className}">
            <div class="carousel-title"><i class='fas ${data.icon} carousel-icon'></i> ${data.name}</div>
            <div class="carousel-img-block">
              <img src="/static/uploads/${data.image}" alt="${data.name}" class="carousel-img" />
            </div>
            <div class="carousel-desc">${data.description}</div>
          </div>
        `;
      });
      // Placer les flèches sous l'image sur mobile
      if (!document.querySelector('.carousel-arrows-bottom')) {
        const arrowsDiv = document.createElement('div');
        arrowsDiv.className = 'carousel-arrows-bottom';
        leftBtn.parentNode.insertBefore(arrowsDiv, coverflow.parentNode.nextSibling);
        arrowsDiv.appendChild(leftBtn);
        arrowsDiv.appendChild(rightBtn);
      }
      return;
    }
    // Desktop: coverflow avec 5 images (état actuel inchangé)
    for (let i = -2; i <= 2; i++) {
      const pos = (idx + i + carouselData.length) % carouselData.length;
      const data = carouselData[pos];
      let className = 'carousel-item';
      if (i === 0) className += ' center';
      else if (i === -1) className += ' left';
      else if (i === 1) className += ' right';
      // Les extrêmes sont plus éloignés
      const style = i === -2 ? 'left:10%;opacity:0.2;z-index:0;' : i === 2 ? 'left:90%;opacity:0.2;z-index:0;' : '';
      coverflow.innerHTML += `
        <div class="${className}" style="${style}">
          <div class="carousel-title">${i === 0 ? `<i class='fas ${data.icon} carousel-icon'></i> ${data.name}` : ''}</div>
          <div class="carousel-img-block">
            <img src="/static/uploads/${data.image}" alt="${data.name}" class="carousel-img" />
          </div>
          <div class="carousel-desc">${i === 0 ? data.description : ''}</div>
        </div>
      `;
    }
    // Remettre les flèches à leur place normale sur desktop
    if (document.querySelector('.carousel-arrows-bottom')) {
      container.insertBefore(leftBtn, container.firstChild);
      container.appendChild(rightBtn);
      document.querySelector('.carousel-arrows-bottom').remove();
    }
  }

  function prev() {
    current = (current - 1 + carouselData.length) % carouselData.length;
    renderCoverflow(current);
  }
  function next() {
    current = (current + 1) % carouselData.length;
    renderCoverflow(current);
  }

  leftBtn.addEventListener('click', prev);
  rightBtn.addEventListener('click', next);

  // Swipe support
  let startX = null;
  coverflow.addEventListener('touchstart', e => {
    startX = e.touches[0].clientX;
  });
  coverflow.addEventListener('touchend', e => {
    if (startX === null) return;
    let dx = e.changedTouches[0].clientX - startX;
    if (dx > 40) prev();
    else if (dx < -40) next();
    startX = null;
  });

  renderCoverflow(current);
});
