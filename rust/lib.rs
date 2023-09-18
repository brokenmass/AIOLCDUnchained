use pyo3::{prelude::*, types::PyBytes};

fn encode(width: u16, height: u16, rgb888_raw: &[u8]) -> Vec<u8> {

  let mut v = Vec::with_capacity(1024 * 1024);
  let mut vec: Vec<u16> = Vec::new();
  for x in (0..rgb888_raw.len()).step_by(3) {
    let r = (rgb888_raw[x + 0] as u32 * 249 + 1014) >> 11;
    let g = (rgb888_raw[x + 1] as u32 * 253 + 505) >> 10;
    let b = (rgb888_raw[x + 2] as u32 * 249 + 1014) >> 11;
    vec.push(((r as u16) << 11) | ((g as u16) << 5) | (b as u16))
}
  let rgb565_raw: &[u16] = unsafe { std::slice::from_raw_parts(vec.as_ptr() as *const u16, vec.len()) };

  q565::encode::Q565EncodeContext::encode_to_vec(
    width as u16,
    height as u16,
    rgb565_raw,
    &mut v
  );

  return v;
}

#[pyfunction]
fn py_encode(py: Python, width: u16, height: u16, rgb888_raw: &[u8]) -> PyObject  {

  let v = py.allow_threads(|| encode(width, height, rgb888_raw));


  return PyBytes::new(py, &v).into();
}

/// A Python module implemented in Rust.
#[pymodule]
fn q565_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_encode, m)?)?;
    Ok(())
}