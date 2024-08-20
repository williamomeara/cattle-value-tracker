import React, { useState, useEffect } from 'react';
import CattleValueCharts from './CattleValueChart';
import '../styles/CattleValueCalculator.css';
import Modal from 'react-modal';

Modal.setAppElement('#root');

const CattleValueCalculator = () => {
  const [cattleData, setCattleData] = useState({ cattle: [] });
  const [cattleList, setCattleList] = useState([]);
  const [newCattleType, setNewCattleType] = useState('');
  const [newCattleWeight, setNewCattleWeight] = useState('');
  const [editingIndex, setEditingIndex] = useState(null);
  const [editingCattleType, setEditingCattleType] = useState('');
  const [editingCattleWeight, setEditingCattleWeight] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedCattle, setSelectedCattle] = useState(null);

  // Load cattle data from JSON and localStorage
  useEffect(() => {
    // Construct the correct URL for GitHub Pages
    const fetchUrl = `${process.env.PUBLIC_URL}/assets/farming_data.json`;
  
    fetch(fetchUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        if (data && Array.isArray(data.cattle)) {
          setCattleData(data);
        } else {
          console.error('Invalid data structure:', data);
          setCattleData({ cattle: [] });
        }
      })
      .catch(error => console.error('Error fetching the JSON data:', error));
  
    // Load cattle list from localStorage
    const savedCattleList = localStorage.getItem('cattleList');
    if (savedCattleList) {
      setCattleList(JSON.parse(savedCattleList));
    }
  }, []);
  

  // Save cattleList to local storage whenever it changes
  useEffect(() => {
    if (cattleList.length > 0) {
      localStorage.setItem('cattleList', JSON.stringify(cattleList));
    }
  }, [cattleList]);

  const handleAddCattle = () => {
    if (newCattleType && newCattleWeight) {
      const newCattleValues = getCattleValues(newCattleType);
      const newCattle = {
        type: newCattleType,
        weight: parseFloat(newCattleWeight),
        values: newCattleValues
      };
      setCattleList([...cattleList, newCattle]);
      setNewCattleType('');
      setNewCattleWeight('');
    }
  };

  const handleRemoveCattle = (index) => {
    const updatedList = cattleList.filter((_, i) => i !== index);
    setCattleList(updatedList);
    if (editingIndex === index) {
      setEditingIndex(null);
    }
  };

  const handleEditCattle = (index) => {
    const cattle = cattleList[index];
    setEditingIndex(index);
    setEditingCattleType(cattle.type);
    setEditingCattleWeight(cattle.weight);
  };

  const saveEditCattle = () => {
    const updatedList = cattleList.map((cattle, i) =>
      i === editingIndex ? { ...cattle, type: editingCattleType, weight: parseFloat(editingCattleWeight), values: getCattleValues(editingCattleType) } : cattle
    );
    setCattleList(updatedList);
    setEditingIndex(null);
    setEditingCattleType('');
    setEditingCattleWeight('');
  };

  const getCattleValues = (type) => {
    const cattle = cattleData.cattle.find(cattle => cattle.type === type);
    return cattle ? cattle.values : [];
  };

  const PlaceholderGraph = () => (
    <div>
      <p>No data available to display.</p>
    </div>
  );

  const handleClearData = () => {
    localStorage.removeItem('cattleList');
    setCattleList([]);
  };

  return (
    <div className="container">
      <h1>Cattle Value Tracker</h1>
      <div className="form-group">
        <select value={newCattleType} onChange={(e) => setNewCattleType(e.target.value)}>
          <option value="">Select Cattle Type</option>
          {cattleData.cattle.length > 0 ? (
            cattleData.cattle.map(cattle => (
              <option key={cattle.type} value={cattle.type}>
                {cattle.type.replace('_', ' ').toUpperCase()}
              </option>
            ))
          ) : (
            <option value="">No Cattle Types Available</option>
          )}
        </select>
        <input
          type="number"
          placeholder="Weight (kg)"
          value={newCattleWeight}
          onChange={(e) => setNewCattleWeight(e.target.value)}
        />
        <button onClick={handleAddCattle}>Add Cattle</button>
      </div>
      <button onClick={handleClearData}>Clear Data</button>
      {cattleList.length === 0 ? (
        <PlaceholderGraph />
      ) : (
        <CattleValueCharts 
          cattleList={cattleList} 
          startDate={startDate} 
          endDate={endDate} 
          selectedCattle={selectedCattle}
        />
      )}
      {cattleData.cattle.length === 0 && (
        <div>
          <p>Loading...</p>
        </div>
      )}
      {cattleList.length > 0 && (
        <div className="cattle-list">
          <h2>Current Cattle List</h2>
          {cattleList.map((cattle, index) => (
            <div className="cattle-item" key={index}>
              <span>{cattle.type.replace('_', ' ').toUpperCase()} - Weight: {cattle.weight} kg</span>
              <div>
                <button onClick={() => handleEditCattle(index)}>
                  Edit
                </button>
                <button onClick={() => handleRemoveCattle(index)}>Remove</button>
              </div>
              {editingIndex === index && (
                <Modal
                  isOpen={editingIndex === index}
                  onRequestClose={() => setEditingIndex(null)}
                  className="modal"
                  overlayClassName="overlay"
                >
                  <h2>Edit Cattle</h2>
                  <select
                    value={editingCattleType}
                    onChange={(e) => setEditingCattleType(e.target.value)}
                  >
                    {cattleData.cattle.map(cattle => (
                      <option key={cattle.type} value={cattle.type}>
                        {cattle.type.replace('_', ' ').toUpperCase()}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    placeholder="Weight (kg)"
                    value={editingCattleWeight}
                    onChange={(e) => setEditingCattleWeight(e.target.value)}
                  />
                  <button onClick={saveEditCattle}>Save Changes</button>
                  <button onClick={() => setEditingIndex(null)}>Cancel</button>
                </Modal>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CattleValueCalculator;
