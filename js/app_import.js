$(document).ready(function(){
  
  // G-Code Canvas Preview
  var icanvas = new Canvas('#import_canvas');
  icanvas.background('ffffff'); 
  // file upload form
  $('#svg_upload_file').change(function(e){
    var input = $('#svg_upload_file').get(0)
    if (typeof window.FileReader !== 'function') {
      $().uxmessage('error', "This requires a modern browser with File API support.");
    } else if (!input.files) {
      $().uxmessage('error', "This browser does not support the files property.");
    } else if (!input.files[0]) {
      $().uxmessage('notice', "No file was selected.");      
    } else {
      var fr = new FileReader()
      fr.onload = parseSvgData
      fr.readAsText(input.files[0])
    }
    
    function parseSvgData(e) {
      $().uxmessage('notice', "parsing SVG ...");
      var svgdata = e.target.result
      //alert(svgdata)
      
      var dpi = parseFloat($('#dpi_value').val());
      var px2mm = 25.4*(1.0/dpi);
      
      var boundarys = SVGReader.parse(svgdata, {})
      //alert(boundarys.toSource());
      //alert(JSON.stringify(boundarys));
      //$().uxmessage('notice', JSON.stringify(boundarys));
      
      var gcode = GcodeWriter.write(boundarys, 2000, 255, px2mm, 0.0, 0.0);
      $('#import_results').text(gcode);
      GcodeReader.parse(gcode, 0.5);
      GcodeReader.draw(icanvas);
    }
    
  	e.preventDefault();		
  });


  // setting up dpi selector
  $("#dpi_radio_set").buttonset();
  $('#dpi_radio_72').click(function(e){
    $('#dpi_value').val('72');
    $('#svg_upload_file').trigger('change');
  });
  $('#dpi_radio_90').click(function(e){
    $('#dpi_value').val('90');
    $('#svg_upload_file').trigger('change');
  });
  $('#dpi_radio_other').click(function(e){
    $('#dpi_radio_set').hide();
    $('#dpi_value_div').show();
  });
  $('#dpi_other_back').click(function(e){
    $('#dpi_value_div').hide();
    $('#dpi_radio_set').show();
    $('#svg_upload_file').trigger('change');
  });  
  $('#dpi_value').blur(function(e){
    $('#svg_upload_file').trigger('change');
  });
  $('#dpi_radio_90').trigger('click').button("refresh");


  // setting up add to queue button
  $("#import_to_queue").button();  
  $("#import_to_queue").click(function(e) {
    var gcodedata = $('#import_results').text();
    var fullpath = $('#svg_upload_file').val();
    var filename = fullpath.split('\\').pop().split('/').pop();
    add_to_job_queue(gcodedata, filename);
	  $().uxmessage('notice', "file added to laser job queue");    
  	return false;
  });


});  // ready
