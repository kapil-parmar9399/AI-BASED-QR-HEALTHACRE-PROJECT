document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.feature-card').forEach((el, idx) => {
        el.style.opacity = 0;
        el.style.transform = 'translateY(12px)';
        setTimeout(() => {
            el.style.transition = 'opacity .6s ease, transform .6s ease';
            el.style.opacity = 1;
            el.style.transform = 'translateY(0)';
        }, 120 * idx);
    });

    const hero = document.querySelector('.hero-title');
    if (hero) {
        hero.style.opacity = 0;
        hero.style.transform = 'translateY(6px)';
        setTimeout(() => { hero.style.transition = 'opacity .6s ease, transform .6s ease';
            hero.style.opacity = 1;
            hero.style.transform = 'translateY(0)'; }, 80);
    }
});