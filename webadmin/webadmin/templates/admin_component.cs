<h2>Manage Components</h2>

<?cs if admin.component.name ?>

<form class="float-left" method="post">
  <fieldset class="align-right">
   <legend>Modify Component:</legend>
   <label for="name">Name:</label>
   <input type="text" name="name" id="name" 
          value="<?cs var:admin.component.name ?>">
   <br />
   <label for="owner">Owner:</label>
   <input type="text" name="owner" id="owner" 
          value="<?cs var:admin.component.owner ?>">
   <br />
   <input type="submit" name="cancel" value="Cancel">
   <input type="submit" name="remove" value="Remove">
   <input type="submit" name="save" value="Save">
  </fieldset>
</form>

<?cs else ?>

  <table class="listing" id="complist">
   <thead>
    <tr><th>Name</th><th>Owner</th></tr>
   </thead><?cs
   each:comp = admin.components ?>
   <tr>
    <td><a href="<?cs var:comp.href?>"><?cs var:comp.name ?></a></td>
    <td><?cs var:comp.owner ?></td>
   </tr><?cs
   /each ?>
  </table>
  <br /><br />
  <form class="float-left align-right" method="post">
   <fieldset>
    <legend>Add Component:</legend>
    <label for="name">Name:</label>
    <input type="text" name="name" id="name">
    <br />
    <label for="owner">Owner:</label>
    <input type="text" name="owner" id="owner">
    <br />
    <input type="submit" name="add" value="Add">
   </fieldset>
  </form>

<?cs /if ?>
