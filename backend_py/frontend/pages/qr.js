import { useState } from 'react';

export default function QR() {
    const [input, setInput] = useState('');
    const [result, setResult] = useState(null);

    const handleScan = () => {
        // placeholder scanning logic
        setResult(`Scanned: ${input}`);
    };

    return ( <
        div className = "container" >
        <
        h1 > QR Scanner < /h1> <
        input placeholder = "Paste QR URL"
        value = { input }
        onChange = { e => setInput(e.target.value) }
        /> <
        button onClick = { handleScan } > Scan < /button> {
            result && < p > { result } < /p>} <
                /div>
        );
    }