import { describe, it, expect } from 'vitest';
import {
  parseDSL,
  toDSL,
  formatRef,
  refToUrl,
  type RefArticulo,
  type ApartadosIndex,
} from './dsl-parser';

// Índice de prueba con artículos que tienen apartados
const testApartadosIndex: ApartadosIndex = {
  cpeum: ['2o', '6o', '20', '26', '72', '102', '122', '123', '136'],
  cff: ['27', '28', '32-B', '46-A'],
  lisr: ['82 Quáter', '176', '209'],
};

describe('parseDSL', () => {
  describe('referencias simples', () => {
    it('parsea artículo simple', () => {
      const result = parseDSL('cpeum:123');
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(1);
      expect(result.referencias[0]).toEqual({
        ley: 'cpeum',
        articulo: '123',
      });
    });

    it('parsea artículo ordinal', () => {
      const result = parseDSL('cff:5o');
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('5o');
    });

    it('parsea regla RMF', () => {
      const result = parseDSL('rmf:2.1.36');
      expect(result.success).toBe(true);
      expect(result.referencias[0]).toEqual({
        ley: 'rmf',
        articulo: '2.1.36',
      });
    });

    it('parsea regla RMF con 4 niveles', () => {
      const result = parseDSL('rmf:3.21.2.1');
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('3.21.2.1');
    });
  });

  describe('artículos con sufijo', () => {
    it('parsea artículo con sufijo letra', () => {
      const result = parseDSL('cff:5-A');
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('5-A');
    });

    it('parsea artículo con sufijo BIS', () => {
      const result = parseDSL('lisr:5o-BIS');
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('5o-BIS');
    });

    it('parsea artículo 14-B con modificadores', () => {
      const result = parseDSL('cff:14-B/II/a');
      expect(result.success).toBe(true);
      expect(result.referencias[0]).toEqual({
        ley: 'cff',
        articulo: '14-B',
        fraccion: 'II',
        inciso: 'a',
      });
    });
  });

  describe('modificadores jerárquicos', () => {
    it('parsea apartado', () => {
      const result = parseDSL('cpeum:123/A', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias[0].apartado).toBe('A');
    });

    it('parsea apartado + fracción', () => {
      const result = parseDSL('cpeum:123/A/IX', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias[0]).toEqual({
        ley: 'cpeum',
        articulo: '123',
        apartado: 'A',
        fraccion: 'IX',
      });
    });

    it('parsea jerarquía completa', () => {
      const result = parseDSL('cpeum:123/A/IX/e', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias[0]).toEqual({
        ley: 'cpeum',
        articulo: '123',
        apartado: 'A',
        fraccion: 'IX',
        inciso: 'e',
      });
    });

    it('parsea con numeral', () => {
      const result = parseDSL('cff:9o/II/a/1');
      expect(result.success).toBe(true);
      expect(result.referencias[0]).toEqual({
        ley: 'cff',
        articulo: '9o',
        fraccion: 'II',
        inciso: 'a',
        numeral: '1',
      });
    });

    it('parsea fracción sin apartado', () => {
      const result = parseDSL('lisr:28/XXX');
      expect(result.success).toBe(true);
      expect(result.referencias[0]).toEqual({
        ley: 'lisr',
        articulo: '28',
        fraccion: 'XXX',
      });
    });
  });

  describe('desambiguación artículo vs apartado', () => {
    it('5-A es artículo (con guión)', () => {
      const result = parseDSL('lisr:5-A');
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('5-A');
      expect(result.referencias[0].apartado).toBeUndefined();
    });

    it('5/A sin índice es fracción A (no apartado)', () => {
      // Sin índice de apartados, se asume que es fracción
      const result = parseDSL('lisr:5/A');
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('5');
      expect(result.referencias[0].fraccion).toBe('A');
      expect(result.referencias[0].apartado).toBeUndefined();
    });

    it('123/A con índice es apartado A (artículo en índice)', () => {
      // El artículo 123 de CPEUM está en el índice de apartados
      const result = parseDSL('cpeum:123/A', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('123');
      expect(result.referencias[0].apartado).toBe('A');
      expect(result.referencias[0].fraccion).toBeUndefined();
    });

    it('140/I sin apartados es fracción I', () => {
      // El artículo 140 de LISR NO tiene apartados
      const result = parseDSL('lisr:140/I', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias[0].articulo).toBe('140');
      expect(result.referencias[0].fraccion).toBe('I');
      expect(result.referencias[0].apartado).toBeUndefined();
    });
  });

  describe('listas de artículos', () => {
    it('parsea lista simple', () => {
      const result = parseDSL('cpeum:94,97,116');
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(3);
      expect(result.referencias.map(r => r.articulo)).toEqual(['94', '97', '116']);
    });

    it('parsea lista con modificador en último', () => {
      const result = parseDSL('cpeum:94,97,116/III');
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(3);
      expect(result.referencias[2].fraccion).toBe('III');
    });

    it('parsea lista con modificadores mezclados', () => {
      const result = parseDSL('cpeum:122/A/IV,123/A/IX', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(2);
      expect(result.referencias[0].apartado).toBe('A');
      expect(result.referencias[0].fraccion).toBe('IV');
      expect(result.referencias[1].apartado).toBe('A');
      expect(result.referencias[1].fraccion).toBe('IX');
    });
  });

  describe('múltiples leyes', () => {
    it('parsea dos leyes', () => {
      const result = parseDSL('lisr:28/XXX+cff:33');
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(2);
      expect(result.referencias[0].ley).toBe('lisr');
      expect(result.referencias[1].ley).toBe('cff');
    });

    it('parsea tres leyes', () => {
      const result = parseDSL('cpeum:123/A+lisr:94+lft:132', testApartadosIndex);
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(3);
      expect(result.referencias[0].apartado).toBe('A');
    });
  });

  describe('rangos', () => {
    it('parsea rango simple', () => {
      const result = parseDSL('cff:1..5');
      expect(result.success).toBe(true);
      expect(result.referencias).toHaveLength(5);
      expect(result.referencias.map(r => r.articulo)).toEqual(['1', '2', '3', '4', '5']);
    });

    it('rechaza rango invertido', () => {
      const result = parseDSL('cff:5..1');
      expect(result.success).toBe(false);
      expect(result.error).toContain('invertido');
    });

    it('rechaza rango demasiado grande', () => {
      const result = parseDSL('cff:1..200');
      expect(result.success).toBe(false);
      expect(result.error).toContain('grande');
    });
  });

  describe('errores', () => {
    it('rechaza query vacía', () => {
      const result = parseDSL('');
      expect(result.success).toBe(false);
    });

    it('rechaza ley desconocida', () => {
      const result = parseDSL('xyz:123');
      expect(result.success).toBe(false);
      expect(result.error).toContain('desconocida');
    });

    it('rechaza sin separador', () => {
      const result = parseDSL('cpeum123');
      expect(result.success).toBe(false);
      expect(result.error).toContain(':');
    });

    it('rechaza sin artículo', () => {
      const result = parseDSL('cpeum:');
      expect(result.success).toBe(false);
    });

    it('rechaza modificadores en orden incorrecto', () => {
      // inciso antes de fracción
      const result = parseDSL('lisr:28/a/I');
      expect(result.success).toBe(false);
    });
  });
});

describe('toDSL', () => {
  it('convierte referencia simple', () => {
    const refs: RefArticulo[] = [{ ley: 'cpeum', articulo: '123' }];
    expect(toDSL(refs)).toBe('cpeum:123');
  });

  it('convierte referencia con modificadores', () => {
    const refs: RefArticulo[] = [{
      ley: 'cpeum',
      articulo: '123',
      apartado: 'A',
      fraccion: 'IX',
      inciso: 'e',
    }];
    expect(toDSL(refs)).toBe('cpeum:123/A/IX/e');
  });

  it('convierte lista de misma ley', () => {
    const refs: RefArticulo[] = [
      { ley: 'cpeum', articulo: '94' },
      { ley: 'cpeum', articulo: '97' },
      { ley: 'cpeum', articulo: '116', fraccion: 'III' },
    ];
    expect(toDSL(refs)).toBe('cpeum:94,97,116/III');
  });

  it('convierte múltiples leyes', () => {
    const refs: RefArticulo[] = [
      { ley: 'lisr', articulo: '28', fraccion: 'XXX' },
      { ley: 'cff', articulo: '33' },
    ];
    expect(toDSL(refs)).toBe('lisr:28/XXX+cff:33');
  });

  it('round-trip mantiene equivalencia', () => {
    const queries = [
      'cpeum:123',
      'cpeum:123/A/IX/e',
      'lisr:28/XXX',
      'cpeum:94,97,116/III',
      'lisr:28/XXX+cff:33',
    ];

    for (const query of queries) {
      const parsed = parseDSL(query, testApartadosIndex);
      expect(parsed.success).toBe(true);
      expect(toDSL(parsed.referencias)).toBe(query);
    }
  });
});

describe('formatRef', () => {
  it('formatea artículo simple', () => {
    expect(formatRef({ ley: 'cpeum', articulo: '123' }))
      .toBe('CPEUM Art. 123');
  });

  it('formatea con apartado', () => {
    expect(formatRef({ ley: 'cpeum', articulo: '123', apartado: 'A' }))
      .toBe('CPEUM Art. 123, Apartado A');
  });

  it('formatea jerarquía completa', () => {
    expect(formatRef({
      ley: 'cpeum',
      articulo: '123',
      apartado: 'A',
      fraccion: 'IX',
      inciso: 'e',
    })).toBe('CPEUM Art. 123, Apartado A, Fracción IX, Inciso e');
  });

  it('formatea regla RMF', () => {
    expect(formatRef({ ley: 'rmf', articulo: '2.1.36' }))
      .toBe('RMF Regla 2.1.36');
  });

  it('formatea regla RMF con fracción', () => {
    expect(formatRef({ ley: 'rmf', articulo: '2.1.36', fraccion: 'I' }))
      .toBe('RMF Regla 2.1.36, Fracción I');
  });
});

describe('refToUrl', () => {
  it('genera URL para artículo simple', () => {
    expect(refToUrl({ ley: 'cpeum', articulo: '123' }))
      .toBe('/cpeum/articulo/123/');
  });

  it('genera URL para artículo con sufijo', () => {
    expect(refToUrl({ ley: 'cff', articulo: '14-B' }))
      .toBe('/cff/articulo/14-B/');
  });

  it('genera URL para regla RMF', () => {
    expect(refToUrl({ ley: 'rmf', articulo: '2.1.36' }))
      .toBe('/rmf/articulo/2.1.36/');
  });
});
